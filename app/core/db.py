import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    # Use DB_POOLER_URL for normal application connections
    db_url = os.getenv('DB_POOLER_URL')
    if not db_url:
        raise ValueError("Database URL not found in environment variables.")
    
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    return conn
