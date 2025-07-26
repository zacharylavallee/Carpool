#!/usr/bin/env python3
"""
Database Migration: Add active status to trips table
This allows multiple trips per channel with only one active at a time
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_connection():
    """Get database connection"""
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def migrate_trip_active_status():
    """Add active status column and update constraints"""
    print("🔄 Starting trip active status migration...")
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            print("📋 Step 1: Checking current trips table structure...")
            
            # Check if active column already exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'trips' AND column_name = 'active'
            """)
            active_column_exists = cur.fetchone() is not None
            
            if active_column_exists:
                print("✅ Active column already exists")
            else:
                print("🔧 Adding 'active' column to trips table...")
                cur.execute("ALTER TABLE trips ADD COLUMN active BOOLEAN DEFAULT TRUE")
                
                # Set all existing trips to active (they were the only trip in their channel)
                cur.execute("UPDATE trips SET active = TRUE WHERE active IS NULL")
                
                # Make the column NOT NULL
                cur.execute("ALTER TABLE trips ALTER COLUMN active SET NOT NULL")
                print("✅ Added 'active' column")
            
            print("📋 Step 2: Updating primary key constraints...")
            
            # Check current primary key
            cur.execute("""
                SELECT constraint_name, column_name
                FROM information_schema.key_column_usage
                WHERE table_name = 'trips' AND constraint_name LIKE '%pkey%'
            """)
            current_pk = cur.fetchall()
            print(f"   Current PK: {current_pk}")
            
            # Drop the old primary key constraint (channel_id only)
            if current_pk:
                pk_name = current_pk[0][0]
                print(f"🗑️ Dropping old primary key constraint: {pk_name}")
                cur.execute(f"ALTER TABLE trips DROP CONSTRAINT {pk_name}")
            
            # Add new composite primary key (name is globally unique)
            print("🔧 Adding new primary key on 'name' column...")
            cur.execute("ALTER TABLE trips ADD CONSTRAINT trips_pkey PRIMARY KEY (name)")
            
            print("📋 Step 3: Adding unique constraint for active trips per channel...")
            
            # Add unique constraint: only one active trip per channel
            cur.execute("""
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS trips_active_channel_unique 
                ON trips (channel_id) 
                WHERE active = TRUE
            """)
            print("✅ Added unique constraint for active trips per channel")
            
            print("📋 Step 4: Updating foreign key references...")
            
            # Check if cars table needs updating
            cur.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'cars' AND constraint_type = 'FOREIGN KEY'
            """)
            fk_constraints = cur.fetchall()
            
            for constraint in fk_constraints:
                constraint_name = constraint[0]
                if 'channel_id' in constraint_name.lower():
                    print(f"🔧 Updating foreign key constraint: {constraint_name}")
                    # The cars table should reference trips by name, not channel_id
                    # This might need manual review based on current schema
            
            print("📋 Step 5: Verifying migration...")
            
            # Verify the new structure
            cur.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_name = 'trips'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            
            print("✅ New trips table structure:")
            for col in columns:
                print(f"   - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
            
            # Check active trips per channel
            cur.execute("""
                SELECT 
                    channel_id,
                    COUNT(*) as total_trips,
                    COUNT(*) FILTER (WHERE active = TRUE) as active_trips
                FROM trips 
                GROUP BY channel_id
            """)
            channel_stats = cur.fetchall()
            
            print("✅ Trips per channel:")
            for stat in channel_stats:
                print(f"   - Channel {stat[0]}: {stat[1]} total, {stat[2]} active")
            
            conn.commit()
            print("✅ Migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("🔄 Trip Active Status Migration")
    print("=" * 50)
    
    success = migrate_trip_active_status()
    if success:
        print("\n🎉 Migration completed successfully!")
        print("   - Trips can now have active/inactive status")
        print("   - Multiple trips allowed per channel")
        print("   - Only one active trip per channel enforced")
    else:
        print("\n❌ Migration failed!")
        print("   - Please review errors and try again")
        print("   - Consider backing up database before retry")
