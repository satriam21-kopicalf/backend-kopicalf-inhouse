import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import time
import threading

load_dotenv()

# Pool size: workers hold 1 conn per nested task stage; keep headroom to avoid
# "connection pool exhausted" at celery concurrency 8+
POOL_MAX = int(os.getenv('DB_POOL_MAX', '20'))

# Global connection pool with lock for thread safety
_connection_pool = None
_pool_lock = threading.Lock()

def _get_pool():
    """Get or create the connection pool (singleton pattern)."""
    global _connection_pool

    if _connection_pool is not None:
        return _connection_pool

    with _pool_lock:
        # Double-check after acquiring lock
        if _connection_pool is not None:
            return _connection_pool

        # Use direct URL to avoid pooler limit issues
        db_url = os.getenv('DB_DIRECT_URL') or os.getenv('DATABASE_URL')
        pooler_url = os.getenv('DB_POOLER_URL')

        import re
        match = None

        # Try direct URL first
        if db_url:
            match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
            if match:
                user, password, host, port, dbname = match.groups()
                try:
                    _connection_pool = pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=POOL_MAX,
                        database=dbname,
                        user=user,
                        password=password,
                        host=host,
                        port=port,
                        options="-c search_path=esb_data,public"
                    )
                    print(f"[DB] Pool created (direct): min=2, max={POOL_MAX}")
                    return _connection_pool
                except Exception as e:
                    print(f"[DB] Direct connection failed: {e}")
                    _connection_pool = None

        # Fallback to pooler
        if pooler_url:
            match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', pooler_url)
            if match:
                user, password, host, port, dbname = match.groups()
                try:
                    _connection_pool = pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=POOL_MAX,
                        database=dbname,
                        user=user,
                        password=password,
                        host=host,
                        port=port,
                        options="-c search_path=esb_data,public"
                    )
                    print(f"[DB] Pool created (pooler): min=2, max={POOL_MAX}")
                    return _connection_pool
                except Exception as e:
                    print(f"[DB] Pooler connection failed: {e}")
                    _connection_pool = None

        raise ValueError("No valid database URL found")


def _conn_alive(conn):
    """Validate a pooled connection is actually usable (drops stale ones)."""
    try:
        if conn.closed:
            return False
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.rollback()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def get_db_connection():
    """Get a live connection from the pool (stale connections are recycled)."""
    max_retries = 5

    for attempt in range(max_retries):
        try:
            p = _get_pool()
            conn = p.getconn()
            if not _conn_alive(conn):
                print(f"[DB] Stale pooled connection discarded (attempt {attempt + 1})")
                try:
                    p.putconn(conn, close=True)
                except Exception:
                    pass
                continue
            conn.autocommit = False
            return conn
        except psycopg2.pool.PoolError as e:
            if attempt < max_retries - 1:
                print(f"[DB] Pool exhausted, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(0.5 * (attempt + 1))
                # Reset pool on exhaustion
                global _connection_pool
                with _pool_lock:
                    if _connection_pool:
                        try:
                            _connection_pool.closeall()
                        except:
                            pass
                        _connection_pool = None
                continue
            print(f"[DB] Pool exhausted after retries: {e}")
            raise
        except Exception as e:
            print(f"[DB] Connection error: {e}")
            raise


def return_connection(conn):
    """Return a connection to the pool."""
    global _connection_pool
    if _connection_pool and conn:
        try:
            _connection_pool.putconn(conn)
        except Exception as e:
            print(f"[DB] Error returning connection: {e}")
            try:
                conn.close()
            except:
                pass


def close_all_connections():
    """Close all connections in the pool."""
    global _connection_pool
    with _pool_lock:
        if _connection_pool:
            try:
                _connection_pool.closeall()
            except:
                pass
            _connection_pool = None
            print("[DB] All connections closed")


class PooledConnection:
    """Context manager for pooled database connections."""

    def __init__(self):
        self.conn = None
        self.cur = None

    def __enter__(self):
        self.conn = get_db_connection()
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        return self.conn, self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cur:
            try:
                self.cur.close()
            except:
                pass
        if self.conn:
            if exc_type is None:
                try:
                    self.conn.commit()
                except:
                    self.conn.rollback()
            else:
                try:
                    self.conn.rollback()
                except:
                    pass
            return_connection(self.conn)
        return False


def get_db_connection_legacy():
    """Legacy single-connection version."""
    db_url = os.getenv('DB_DIRECT_URL') or os.getenv('DATABASE_URL')
    if not db_url:
        db_url = os.getenv('DB_POOLER_URL')
    if not db_url:
        raise ValueError("No database URL found")
    conn = psycopg2.connect(
        db_url,
        cursor_factory=RealDictCursor,
        options="-c search_path=esb_data,public"
    )
    return conn
