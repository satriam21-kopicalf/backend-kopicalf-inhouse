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
    
    # Set search_path to prioritize esb_data schema, then fall back to public
    # This allows queries to find tables in esb_data first, then public
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, options="-c search_path=esb_data,public")
    return conn
