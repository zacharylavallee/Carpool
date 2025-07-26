#!/usr/bin/env python3
"""
Migration script to enforce one trip per channel
This updates the trips table schema and cleans up duplicate trips
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

def migrate_one_trip_per_channel():
    """Update trips table to enforce one trip per channel"""
    with get_conn() as conn:
        cur = conn.cursor()
        
        print("Migrating trips table to enforce one trip per channel...")
        
        try:
            # First, identify and handle duplicate trips per channel
            print("Checking for multiple trips per channel...")
            cur.execute("""
                SELECT channel_id, COUNT(*) as trip_count, array_agg(name) as trip_names
                FROM trips 
                GROUP BY channel_id 
                HAVING COUNT(*) > 1
            """)
            duplicates = cur.fetchall()
            
            if duplicates:
                print(f"Found {len(duplicates)} channels with multiple trips:")
                for channel_id, count, names in duplicates:
                    print(f"  Channel {channel_id}: {count} trips - {names}")
                    # Keep the most recent trip, delete others
                    cur.execute("""
                        DELETE FROM trips 
                        WHERE channel_id = %s 
                        AND created_at < (
                            SELECT MAX(created_at) 
                            FROM trips 
                            WHERE channel_id = %s
                        )
                    """, (channel_id, channel_id))
                    print(f"    Kept most recent trip, deleted {count-1} older trips")
            else:
                print("No duplicate trips found.")
            
            # Create new trips table with correct schema
            cur.execute("""
                CREATE TABLE trips_new (
                    name TEXT NOT NULL,
                    channel_id TEXT NOT NULL UNIQUE,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(channel_id)
                )
            """)
            
            # Copy remaining data to new table
            cur.execute("""
                INSERT INTO trips_new (name, channel_id, created_by, created_at)
                SELECT name, channel_id, created_by, created_at
                FROM trips
            """)
            
            # Drop old table and rename new one
            cur.execute("DROP TABLE trips CASCADE")
            cur.execute("ALTER TABLE trips_new RENAME TO trips")
            
            # Recreate foreign key constraints for cars table
            cur.execute("""
                ALTER TABLE cars 
                ADD CONSTRAINT cars_channel_id_fkey 
                FOREIGN KEY (channel_id) REFERENCES trips(channel_id) ON DELETE CASCADE
            """)
            
            conn.commit()
            print("✅ Successfully migrated trips table to enforce one trip per channel")
            
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    migrate_one_trip_per_channel()
