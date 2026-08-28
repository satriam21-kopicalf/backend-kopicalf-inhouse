"""
Migration script to apply ESB data schema to Supabase database.
This script applies the SQL migration files in the correct order.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Get database connection for migrations using pooler for better connectivity."""
    db_url = os.getenv('DB_POOLER_URL') or os.getenv('DATABASE_URL') or os.getenv('DB_DIRECT_URL')
    if not db_url:
        raise ValueError("Database URL not found in environment variables.")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def run_migration_file(filename, description):
    """Run a single migration file."""
    file_path = f"supabase/migrations/{filename}"
    if not os.path.exists(file_path):
        print(f"Migration file not found: {file_path}")
        return False
    
    print(f"Running {description}: {filename}")
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        cur.execute(sql)
        conn.commit()
        
        print(f"Completed: {description}")
        return True
        
    except Exception as e:
        print(f"Failed {description}: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def check_migration_status():
    """Check current migration status."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Check if esb_data schema exists
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name = 'esb_data'
        """)
        esb_schema_exists = cur.fetchone() is not None
        
        # Check if master tables exist
        cur.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables 
            WHERE table_schema = 'esb_data' AND table_name LIKE 'master_%'
        """)
        master_tables_count = cur.fetchone()['count']
        
        # Check if report tables exist
        cur.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables 
            WHERE table_schema = 'esb_data' AND table_name LIKE 'report_%'
        """)
        report_tables_count = cur.fetchone()['count']
        
        # Check if system tables exist
        cur.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables 
            WHERE table_schema = 'esb_data' AND table_name IN ('company_configs', 'endpoint_registry', 'sync_schedules', 'master_normalization')
        """)
        system_tables_count = cur.fetchone()['count']
        
        return {
            "esb_schema_exists": esb_schema_exists,
            "master_tables_count": master_tables_count,
            "report_tables_count": report_tables_count,
            "system_tables_count": system_tables_count
        }
    finally:
        conn.close()

def main():
    """Main migration execution."""
    print("Starting ESB Data Migration to Supabase")
    print("=" * 60)
    
    # Check current status
    status = check_migration_status()
    print(f"Current Status:")
    print(f"  - esb_data schema: {'Exists' if status['esb_schema_exists'] else 'Not found'}")
    print(f"  - Master tables: {status['master_tables_count']}")
    print(f"  - Report tables: {status['report_tables_count']}")
    print(f"  - System tables: {status['system_tables_count']}")
    print("=" * 60)
    
    # Define migrations in order
    migrations = [
        ("20260822000000_create_esb_data_schema.sql", "Create esb_data schema and system tables"),
        ("20260822010000_create_master_tables.sql", "Create master data tables"),
        ("20260822020000_create_report_tables.sql", "Create report data tables"),
        ("20260822030000_seed_system_data.sql", "Seed system data (companies, endpoints, schedules)")
    ]
    
    # Run migrations
    results = []
    for filename, description in migrations:
        result = run_migration_file(filename, description)
        results.append((filename, result))
    
    # Final status check
    print("\n" + "=" * 60)
    print("Final Migration Status:")
    final_status = check_migration_status()
    print(f"  - esb_data schema: {'Exists' if final_status['esb_schema_exists'] else 'Not found'}")
    print(f"  - Master tables: {final_status['master_tables_count']}")
    print(f"  - Report tables: {final_status['report_tables_count']}")
    print(f"  - System tables: {final_status['system_tables_count']}")
    
    # Summary
    success_count = sum(1 for _, result in results if result)
    print(f"\nMigration Summary: {success_count}/{len(migrations)} completed successfully")
    
    if success_count == len(migrations):
        print("All migrations completed successfully!")
    else:
        print("Some migrations failed. Please check the errors above.")

if __name__ == "__main__":
    main()