#!/usr/bin/env python3
"""Start the backend server with proper environment"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load env vars from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Print debug info
print(f"DB_POOLER_URL: {'Set' if os.getenv('DB_POOLER_URL') else 'NOT SET'}")

# Import and run uvicorn
import uvicorn

if __name__ == '__main__':
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=8005,
        reload=False,
        log_level='info'
    )
