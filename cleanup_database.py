#!/usr/bin/env python3
"""
Database Cleanup Script
Removes unused tables and cleans up the database schema
Run this to clean up the trip_settings table and any other unused database objects
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

def get_connection():
    """Get database connection"""
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def cleanup_database():
    """Clean up unused database objects"""
    print("🧹 Starting database cleanup...")
    print(f"📅 Cleanup run at: {datetime.now().isoformat()}")
    print("=" * 60)
    
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("📋 Step 1: Checking for unused tables...")
        
        # Check if trip_settings table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'trip_settings'
            )
        """)
        trip_settings_exists = cur.fetchone()['exists']
        
        if trip_settings_exists:
            print("🔍 Found trip_settings table")
            
            # Check if it has any data
            cur.execute("SELECT COUNT(*) as count FROM trip_settings")
            record_count = cur.fetchone()['count']
            print(f"   📊 Contains {record_count} records")
            
            if record_count > 0:
                print("⚠️  WARNING: trip_settings table contains data!")
                print("   This script will delete all data in the table.")
                print("   If you need to preserve this data, cancel now (Ctrl+C)")
                input("   Press Enter to continue or Ctrl+C to cancel...")
            
            # Drop the table
            print("🗑️  Removing trip_settings table...")
            cur.execute("DROP TABLE IF EXISTS trip_settings CASCADE")
            print("   ✅ trip_settings table removed successfully")
        else:
            print("✅ trip_settings table not found (already clean)")
        
        print("\n📋 Step 2: Checking for other unused tables...")
        
        # Get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        all_tables = [row['table_name'] for row in cur.fetchall()]
        
        # Expected tables for the carpool bot
        expected_tables = {'trips', 'cars', 'car_members'}
        
        # Find any extra tables
        extra_tables = set(all_tables) - expected_tables
        
        if extra_tables:
            print(f"⚠️  Found {len(extra_tables)} additional tables:")
            for table in extra_tables:
                cur.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cur.fetchone()['count']
                print(f"   - {table}: {count} records")
            
            print("\n   These tables are not part of the core carpool bot schema.")
            print("   Review them manually if you want to remove them.")
        else:
            print("✅ No extra tables found")
        
        print("\n📋 Step 3: Checking for orphaned sequences...")
        
        # Check for sequences
        cur.execute("""
            SELECT schemaname, sequencename 
            FROM pg_sequences 
            WHERE schemaname = 'public'
        """)
        sequences = cur.fetchall()
        
        if sequences:
            print(f"🔢 Found {len(sequences)} sequences:")
            for seq in sequences:
                print(f"   - {seq['sequencename']}")
            print("   Sequences are normal for auto-increment columns")
        else:
            print("✅ No sequences found")
        
        print("\n📋 Step 4: Final verification...")
        
        # Run a quick validation
        cur.execute("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        final_tables = cur.fetchall()
        print("📊 Final database state:")
        for table in final_tables:
            cur.execute(f"SELECT COUNT(*) as count FROM {table['table_name']}")
            record_count = cur.fetchone()['count']
            print(f"   - {table['table_name']}: {table['column_count']} columns, {record_count} records")
        
        print("\n" + "=" * 60)
        print("✅ Database cleanup completed successfully!")
        print("🎯 Your database is now clean and optimized.")
        
        return True

if __name__ == "__main__":
    try:
        success = cleanup_database()
        if success:
            print("\n💡 Recommendation: Run 'python validate_database.py' to verify the cleanup")
        exit(0)
    except Exception as e:
        print(f"❌ Cleanup failed with error: {e}")
        exit(1)
