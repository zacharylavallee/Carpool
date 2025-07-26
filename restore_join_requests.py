#!/usr/bin/env python3
"""
Restore Join Requests Table
Creates the missing join_requests table to match the codebase functionality
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

def restore_join_requests_table():
    """Restore the join_requests table to match codebase expectations"""
    print("🔄 Restoring join_requests table...")
    print(f"📅 Restoration run at: {datetime.now().isoformat()}")
    print("=" * 60)
    
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("📋 Step 1: Checking if join_requests table exists...")
        
        # Check if table already exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'join_requests'
            )
        """)
        table_exists = cur.fetchone()['exists']
        
        if table_exists:
            print("✅ join_requests table already exists")
            
            # Check structure
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'join_requests' 
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            print("   📊 Current structure:")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"      - {col['column_name']}: {col['data_type']} {nullable}")
        else:
            print("🔧 Creating join_requests table...")
            
            # Create the table with proper structure
            cur.execute("""
                CREATE TABLE join_requests (
                    car_id INTEGER REFERENCES cars(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(car_id, user_id)
                )
            """)
            
            print("   ✅ join_requests table created successfully")
            print("   📊 Structure:")
            print("      - car_id: INTEGER (FK to cars.id)")
            print("      - user_id: TEXT NOT NULL")
            print("      - requested_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("      - PRIMARY KEY: (car_id, user_id)")
        
        print("\n📋 Step 2: Verifying table relationships...")
        
        # Check foreign key constraint
        cur.execute("""
            SELECT 
                tc.constraint_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints AS rc
                ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'join_requests'
        """)
        
        foreign_keys = cur.fetchall()
        if foreign_keys:
            print("   ✅ Foreign key constraints:")
            for fk in foreign_keys:
                print(f"      - {fk['constraint_name']}: → {fk['foreign_table_name']}.{fk['foreign_column_name']} (DELETE {fk['delete_rule']})")
        else:
            print("   ⚠️  No foreign key constraints found")
        
        print("\n📋 Step 3: Testing functionality...")
        
        # Count any existing requests
        cur.execute("SELECT COUNT(*) as count FROM join_requests")
        request_count = cur.fetchone()['count']
        print(f"   📊 Current join requests: {request_count}")
        
        print("\n📋 Step 4: Final verification...")
        
        # Verify the table is ready for use
        cur.execute("""
            SELECT 
                t.table_name,
                (SELECT COUNT(*) FROM information_schema.columns 
                 WHERE table_name = t.table_name) as column_count,
                (SELECT COUNT(*) FROM information_schema.table_constraints 
                 WHERE table_name = t.table_name AND constraint_type = 'FOREIGN KEY') as fk_count
            FROM information_schema.tables t
            WHERE t.table_name = 'join_requests'
        """)
        
        table_info = cur.fetchone()
        if table_info:
            print(f"   ✅ Table verified: {table_info['column_count']} columns, {table_info['fk_count']} foreign keys")
        
        print("\n" + "=" * 60)
        print("✅ Join requests table restoration completed!")
        print("🎯 Your join request functionality is now properly supported by the database.")
        print("\n💡 The join request system allows:")
        print("   - Users to request to join cars with `/in CarID`")
        print("   - Car owners to approve/deny requests")
        print("   - Proper capacity management and member approval")
        
        return True

if __name__ == "__main__":
    try:
        success = restore_join_requests_table()
        if success:
            print("\n💡 Recommendation: Run 'python db_sync_checker.py' to verify the sync is now complete")
        exit(0)
    except Exception as e:
        print(f"❌ Restoration failed with error: {e}")
        exit(1)
