#!/usr/bin/env python3
"""
Simple cleanup script to remove trips and cars with empty channel_id values.
This is cleaner than trying to migrate old data.
"""

import os
import psycopg2
import psycopg2.extras
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

def cleanup_old_data():
    """Remove trips and cars with empty channel_id values"""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        print("Checking for old data with empty channel_id...")
        
        # Check what will be deleted
        cur.execute("SELECT name, created_by FROM trips WHERE channel_id = '' OR channel_id IS NULL")
        old_trips = cur.fetchall()
        
        cur.execute("SELECT id, trip, name, created_by FROM cars WHERE channel_id = '' OR channel_id IS NULL")
        old_cars = cur.fetchall()
        
        if old_trips:
            print(f"\nFound {len(old_trips)} trips to delete:")
            for trip in old_trips:
                print(f"  - {trip['name']} (created by {trip['created_by']})")
        
        if old_cars:
            print(f"\nFound {len(old_cars)} cars to delete:")
            for car in old_cars:
                print(f"  - Car {car['id']}: {car['name']} on trip {car['trip']}")
        
        if not old_trips and not old_cars:
            print("✅ No old data found to clean up")
            return
            
        confirm = input(f"\nDelete {len(old_trips)} trips and {len(old_cars)} cars? (y/n): ").strip().lower()
        
        if confirm == 'y':
            # Delete cars first (due to foreign key constraints)
            cur.execute("DELETE FROM cars WHERE channel_id = '' OR channel_id IS NULL")
            cars_deleted = cur.rowcount
            
            # Delete trips
            cur.execute("DELETE FROM trips WHERE channel_id = '' OR channel_id IS NULL")
            trips_deleted = cur.rowcount
            
            conn.commit()
            
            print(f"✅ Deleted {trips_deleted} trips and {cars_deleted} cars")
            print("You can now recreate your trips using /createtrip in the correct channel")
        else:
            print("❌ Cleanup cancelled")

if __name__ == "__main__":
    cleanup_old_data()
