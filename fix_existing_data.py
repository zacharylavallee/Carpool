#!/usr/bin/env python3
"""
Data migration script to fix existing trips and cars that have empty channel_id values.
This will help existing data work with the new channel-aware schema.
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

def fix_existing_data():
    """Fix existing trips and cars with empty channel_id values"""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        print("Checking for trips with empty channel_id...")
        
        # Find trips with empty channel_id
        cur.execute("SELECT name, created_by FROM trips WHERE channel_id = '' OR channel_id IS NULL")
        empty_trips = cur.fetchall()
        
        if empty_trips:
            print(f"Found {len(empty_trips)} trips with empty channel_id:")
            for trip in empty_trips:
                print(f"  - {trip['name']} (created by {trip['created_by']})")
            
            print("\nTo fix this, you need to provide the channel ID where these trips should belong.")
            print("You can find the channel ID by:")
            print("1. Right-clicking on the channel in Slack")
            print("2. Selecting 'Copy link'")
            print("3. The channel ID is the last part of the URL (starts with 'C')")
            print("\nExample: https://app.slack.com/client/T123/C0987654321 -> channel_id is 'C0987654321'")
            
            # For now, let's just show what needs to be fixed
            print("\nTo fix manually, run these SQL commands in your database:")
            for trip in empty_trips:
                print(f"UPDATE trips SET channel_id = 'YOUR_CHANNEL_ID_HERE' WHERE name = '{trip['name']}' AND created_by = '{trip['created_by']}';")
                
        else:
            print("✅ No trips found with empty channel_id")
            
        # Check cars with empty channel_id
        print("\nChecking for cars with empty channel_id...")
        cur.execute("SELECT id, trip, name, created_by FROM cars WHERE channel_id = '' OR channel_id IS NULL")
        empty_cars = cur.fetchall()
        
        if empty_cars:
            print(f"Found {len(empty_cars)} cars with empty channel_id:")
            for car in empty_cars:
                print(f"  - Car {car['id']}: {car['name']} on trip {car['trip']} (created by {car['created_by']})")
                
            print("\nTo fix cars, run these SQL commands:")
            for car in empty_cars:
                print(f"UPDATE cars SET channel_id = 'YOUR_CHANNEL_ID_HERE' WHERE id = {car['id']};")
        else:
            print("✅ No cars found with empty channel_id")

def interactive_fix():
    """Interactive version to fix data with user input"""
    channel_id = input("\nEnter the channel ID where your trips should belong (starts with 'C'): ").strip()
    
    if not channel_id.startswith('C'):
        print("❌ Channel ID should start with 'C'")
        return
        
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Update trips
        cur.execute("UPDATE trips SET channel_id = %s WHERE channel_id = '' OR channel_id IS NULL", (channel_id,))
        trips_updated = cur.rowcount
        
        # Update cars
        cur.execute("UPDATE cars SET channel_id = %s WHERE channel_id = '' OR channel_id IS NULL", (channel_id,))
        cars_updated = cur.rowcount
        
        conn.commit()
        
        print(f"✅ Updated {trips_updated} trips and {cars_updated} cars with channel_id: {channel_id}")

if __name__ == "__main__":
    fix_existing_data()
    
    fix_it = input("\nDo you want to fix the data interactively? (y/n): ").strip().lower()
    if fix_it == 'y':
        interactive_fix()
