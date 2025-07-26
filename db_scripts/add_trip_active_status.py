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
            
            print("📋 Step 2: Handling foreign key dependencies...")
            
            # First, check what foreign keys reference trips
            cur.execute("""
                SELECT 
                    tc.constraint_name,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND ccu.table_name = 'trips'
            """)
            foreign_keys = cur.fetchall()
            print(f"   Foreign keys referencing trips: {foreign_keys}")
            
            # Drop foreign key constraints that reference trips.channel_id
            fk_to_recreate = []
            for fk in foreign_keys:
                constraint_name, table_name, column_name, foreign_table, foreign_column = fk
                if foreign_column == 'channel_id':
                    print(f"🗑️ Dropping foreign key: {constraint_name} on {table_name}({column_name})")
                    cur.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")
                    fk_to_recreate.append((constraint_name, table_name, column_name, foreign_table, foreign_column))
            
            print("📋 Step 3: Updating primary key constraints...")
            
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
            
            # Recreate foreign keys if needed (but they should reference trip name, not channel_id)
            print("📋 Step 4: Updating foreign key references...")
            for constraint_name, table_name, column_name, foreign_table, foreign_column in fk_to_recreate:
                if table_name == 'cars' and column_name == 'channel_id':
                    # The cars table should reference trips by trip name, not channel_id
                    # But first check if cars.trip column exists and references trips properly
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'cars' AND column_name = 'trip'
                    """)
                    trip_column_exists = cur.fetchone() is not None
                    
                    if trip_column_exists:
                        print(f"🔧 Creating foreign key: cars(trip) -> trips(name)")
                        cur.execute("""
                            ALTER TABLE cars 
                            ADD CONSTRAINT cars_trip_fkey 
                            FOREIGN KEY (trip) REFERENCES trips(name) ON DELETE CASCADE
                        """)
                    else:
                        print(f"⚠️ Warning: cars.trip column not found, skipping foreign key recreation")
            
            print("📋 Step 5: Adding unique constraint for active trips per channel...")
            
            # Add unique constraint: only one active trip per channel
            cur.execute("""
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS trips_active_channel_unique 
                ON trips (channel_id) 
                WHERE active = TRUE
            """)
            print("✅ Added unique constraint for active trips per channel")
            
            print("📋 Step 6: Verifying migration...")
            
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
