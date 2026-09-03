import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Global connection pool
_connection_pool = None


def _get_pool():
    """Get or create the connection pool (singleton pattern)."""
    global _connection_pool
    if _connection_pool is None:
        db_url = os.getenv('DB_POOLER_URL')
        if not db_url:
            raise ValueError("Database URL not found in environment variables.")

        # Parse connection parameters from URL
        # Format: postgresql://user:password@host:port/dbname
        import re
        match = re.match(
            r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)',
            db_url
        )
        if match:
            user, password, host, port, dbname = match.groups()
        else:
            # Fallback to direct connection
            raise ValueError(f"Cannot parse DB_POOLER_URL: {db_url}")

        _connection_pool = pool.ThreadedConnectionPool(
            minconn=5,          # Minimum connections
            maxconn=50,         # Maximum connections (increased for concurrent requests)
            database=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
            options="-c search_path=esb_data,public"
        )
        print(f"[DB] Connection pool created: min=5, max=50")
    return _connection_pool


def get_db_connection():
    """Get a connection from the pool."""
    pool = _get_pool()
    try:
        conn = pool.getconn()
        # Ensure search_path is set for each connection
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"[DB] Error getting connection from pool: {e}")
        raise


def return_connection(conn):
    """Return a connection to the pool."""
    global _connection_pool
    if _connection_pool and conn:
        try:
            _connection_pool.putconn(conn)
        except Exception as e:
            print(f"[DB] Error returning connection to pool: {e}")


def close_all_connections():
    """Close all connections in the pool (call on shutdown)."""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
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
            self.cur.close()
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            return_connection(self.conn)
        return False  # Don't suppress exceptions


# Keep the old function for backward compatibility
def get_db_connection_legacy():
    """Legacy single-connection version (no pooling)."""
    db_url = os.getenv('DB_POOLER_URL')
    if not db_url:
        raise ValueError("Database URL not found in environment variables.")
    conn = psycopg2.connect(
        db_url,
        cursor_factory=RealDictCursor,
        options="-c search_path=esb_data,public"
    )
    return conn
