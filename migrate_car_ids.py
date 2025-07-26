#!/usr/bin/env python3
"""
Migration script to update cars table to support custom ID assignment
This removes the SERIAL constraint and allows manual ID assignment
"""

import os
import psycopg2
from dotenv import load_dotenv, find_dotenv

# Load environment variables
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set")
    exit(1)

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def migrate_car_ids():
    """Update cars table to support custom ID assignment"""
    with get_conn() as conn:
        cur = conn.cursor()
        
        print("Migrating cars table to support custom ID assignment...")
        
        try:
            # Create a new cars table without SERIAL constraint
            cur.execute("""
                CREATE TABLE cars_new (
                    id INTEGER PRIMARY KEY,
                    trip TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    seats INTEGER NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(channel_id) REFERENCES trips(channel_id) ON DELETE CASCADE,
                    UNIQUE(trip, channel_id, created_by)
                )
            """)
            
            # Copy data from old table to new table
            cur.execute("""
                INSERT INTO cars_new (id, trip, channel_id, name, seats, created_by, created_at)
                SELECT id, trip, channel_id, name, seats, created_by, created_at
                FROM cars
            """)
            
            # Drop the old table and rename the new one
            cur.execute("DROP TABLE cars CASCADE")
            cur.execute("ALTER TABLE cars_new RENAME TO cars")
            
            # Recreate foreign key constraints for dependent tables
            cur.execute("""
                ALTER TABLE car_members 
                ADD CONSTRAINT car_members_car_id_fkey 
                FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
            """)
            
            cur.execute("""
                ALTER TABLE join_requests 
                ADD CONSTRAINT join_requests_car_id_fkey 
                FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
            """)
            
            conn.commit()
            print("✅ Successfully migrated cars table to support custom ID assignment")
            
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    migrate_car_ids()
