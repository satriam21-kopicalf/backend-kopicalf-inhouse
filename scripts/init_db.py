import psycopg2
import os
from dotenv import load_dotenv

def init_db():
    load_dotenv()
    
    # We should use DB_POOLER_URL
    db_url = os.getenv('DB_POOLER_URL')
    
    if not db_url:
        print("Error: Database URL not found in environment variables.")
        return

    commands = [
        """
        CREATE TABLE IF NOT EXISTS esb_raw_staging (
            id SERIAL PRIMARY KEY,
            entity_type VARCHAR(50) NOT NULL,
            esb_id VARCHAR(100) NOT NULL,
            raw_data JSONB NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(entity_type, esb_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_history (
            id SERIAL PRIMARY KEY,
            entity_type VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            records_processed INT DEFAULT 0,
            error_message TEXT,
            started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITH TIME ZONE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS dlq_logs (
            id SERIAL PRIMARY KEY,
            entity_type VARCHAR(50) NOT NULL,
            raw_payload JSONB,
            error_reason TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            resolved BOOLEAN DEFAULT FALSE
        );
        """
    ]

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        for cmd in commands:
            cur.execute(cmd)
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize database: {e}")

if __name__ == '__main__':
    init_db()
