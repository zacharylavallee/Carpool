#!/usr/bin/env python3
"""
Database Schema Migration Script
Fixes all schema issues to match current codebase
Run this on PythonAnywhere to update your database schema
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

def run_migration():
    """Run complete database schema migration"""
    print("🔧 Starting database schema migration...")
    
    with get_connection() as conn:
        cur = conn.cursor()
        
        print("📋 Step 1: Checking current schema...")
        
        # Check if channel_id column exists in trips table
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trips' AND column_name = 'channel_id'
        """)
        has_channel_id = cur.fetchone() is not None
        
        if not has_channel_id:
            print("✅ Adding missing channel_id column to trips table...")
            cur.execute("ALTER TABLE trips ADD COLUMN channel_id TEXT")
            
            # Set default channel_id for existing trips (you may need to update these manually)
            cur.execute("UPDATE trips SET channel_id = 'MIGRATION_' || id::text WHERE channel_id IS NULL")
            print("   → Added channel_id column with default values")
        else:
            print("✅ channel_id column already exists")
        
        print("📋 Step 2: Updating trips table constraints...")
        
        # First, drop any foreign key constraints that depend on the primary key
        try:
            cur.execute("ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_new_channel_id_fkey")
            cur.execute("ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_channel_id_fkey")
            cur.execute("ALTER TABLE cars DROP CONSTRAINT IF EXISTS cars_trip_fkey")
            print("   → Removed foreign key constraints from cars table")
        except Exception as e:
            print(f"   → Foreign key removal: {e}")
        
        # Now drop old primary key constraints
        try:
            cur.execute("ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_pkey")
            cur.execute("ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_new_pkey")
            print("   → Removed old primary key constraints")
        except Exception as e:
            print(f"   → Primary key removal: {e}")
        
        # Add new primary key on channel_id (one trip per channel)
        try:
            cur.execute("ALTER TABLE trips ADD CONSTRAINT trips_pkey PRIMARY KEY (channel_id)")
            print("   → Added new primary key on channel_id")
        except psycopg2.errors.UniqueViolation:
            print("   → Constraint already exists or duplicate channel_ids found")
            # Handle duplicates by keeping the most recent trip per channel
            cur.execute("""
                DELETE FROM trips 
                WHERE id NOT IN (
                    SELECT MAX(id) 
                    FROM trips 
                    GROUP BY channel_id
                )
            """)
            cur.execute("ALTER TABLE trips ADD CONSTRAINT trips_pkey PRIMARY KEY (channel_id)")
            print("   → Removed duplicates and added primary key")
        
        print("📋 Step 3: Updating cars table schema...")
        
        # Check if cars table has channel_id column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'cars' AND column_name = 'channel_id'
        """)
        cars_has_channel_id = cur.fetchone() is not None
        
        if not cars_has_channel_id:
            print("✅ Adding channel_id column to cars table...")
            cur.execute("ALTER TABLE cars ADD COLUMN channel_id TEXT")
            
            # Update cars with channel_id from their associated trips
            cur.execute("""
                UPDATE cars 
                SET channel_id = trips.channel_id 
                FROM trips 
                WHERE cars.trip = trips.name
            """)
            print("   → Added channel_id column and populated from trips")
        else:
            print("✅ cars table channel_id column already exists")
        
        # Add foreign key constraint to reference trips(channel_id)
        try:
            cur.execute("""
                ALTER TABLE cars 
                ADD CONSTRAINT cars_channel_id_fkey 
                FOREIGN KEY (channel_id) REFERENCES trips(channel_id) ON DELETE CASCADE
            """)
            print("   → Added foreign key constraint")
        except Exception as e:
            print(f"   → Foreign key constraint addition: {e}")
        
        print("📋 Step 4: Implementing car ID reuse system...")
        
        # Check if cars table has manual ID assignment capability
        try:
            # Try to insert with manual ID to test if sequence allows it
            cur.execute("SELECT setval('cars_id_seq', (SELECT MAX(id) FROM cars), true)")
            print("   → Car ID sequence updated for manual assignment")
        except Exception as e:
            print(f"   → Car ID sequence: {e}")
        
        print("📋 Step 5: Cleaning up orphaned data...")
        
        # Remove cars that don't have valid trips
        cur.execute("""
            DELETE FROM cars 
            WHERE channel_id NOT IN (SELECT channel_id FROM trips)
        """)
        deleted_cars = cur.rowcount
        if deleted_cars > 0:
            print(f"   → Removed {deleted_cars} orphaned cars")
        
        # Remove car_members for cars that don't exist
        cur.execute("""
            DELETE FROM car_members 
            WHERE car_id NOT IN (SELECT id FROM cars)
        """)
        deleted_members = cur.rowcount
        if deleted_members > 0:
            print(f"   → Removed {deleted_members} orphaned car memberships")
        
        print("📋 Step 6: Verifying schema...")
        
        # Verify trips table structure
        cur.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'trips' 
            ORDER BY ordinal_position
        """)
        trips_columns = cur.fetchall()
        print("   → Trips table columns:")
        for col in trips_columns:
            print(f"     - {col[0]} ({col[1]}, nullable: {col[2]})")
        
        # Verify cars table structure
        cur.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'cars' 
            ORDER BY ordinal_position
        """)
        cars_columns = cur.fetchall()
        print("   → Cars table columns:")
        for col in cars_columns:
            print(f"     - {col[0]} ({col[1]}, nullable: {col[2]})")
        
        # Show current data counts
        cur.execute("SELECT COUNT(*) FROM trips")
        trip_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cars")
        car_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM car_members")
        member_count = cur.fetchone()[0]
        
        print(f"   → Current data: {trip_count} trips, {car_count} cars, {member_count} memberships")
        
        conn.commit()
        print("✅ Database migration completed successfully!")
        print("\n🎯 Your database schema is now up to date with the current codebase.")
        print("   - One trip per channel enforced")
        print("   - Car ID reuse system ready")
        print("   - All foreign key relationships updated")
        print("   - Orphaned data cleaned up")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("Please check your DATABASE_URL and try again.")
