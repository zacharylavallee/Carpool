#!/usr/bin/env python3
"""
Debug script to investigate why Home Tab shows "No active trips found"
Checks database schema and actual trip data
"""

import psycopg2
import psycopg2.extras
from config.database import get_conn

def check_trips_table_schema():
    """Check the trips table schema to see if 'active' column exists"""
    print("=== TRIPS TABLE SCHEMA ===")
    
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Get table schema
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'trips'
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        
        if not columns:
            print("❌ trips table does not exist!")
            return False
            
        print("Columns in trips table:")
        has_active_column = False
        for col in columns:
            column_name, data_type, is_nullable, column_default = col
            print(f"  - {column_name}: {data_type} (nullable: {is_nullable}, default: {column_default})")
            if column_name == 'active':
                has_active_column = True
        
        return has_active_column

def check_actual_trips():
    """Check what trips actually exist in the database"""
    print("\n=== ACTUAL TRIPS DATA ===")
    
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get all trips (without active filter)
        cur.execute("SELECT * FROM trips ORDER BY channel_id")
        trips = cur.fetchall()
        
        if not trips:
            print("❌ No trips found in database at all!")
            return
            
        print(f"Found {len(trips)} trips:")
        for trip in trips:
            print(f"  - Trip: '{trip['name']}' (channel: {trip['channel_id']}, created_by: {trip['created_by']})")
            
            # Check if this trip has an 'active' column and its value
            if 'active' in trip.keys():
                print(f"    Active status: {trip['active']}")
            else:
                print(f"    ⚠️  No 'active' column found")

def check_home_tab_query():
    """Test the exact query used by the Home Tab"""
    print("\n=== HOME TAB QUERY TEST ===")
    
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            # This is the exact query from home_tab.py
            cur.execute("SELECT name, channel_id, created_by FROM trips WHERE active=TRUE ORDER BY name")
            trips = cur.fetchall()
            
            print(f"Home Tab query returned {len(trips)} trips:")
            for trip in trips:
                print(f"  - {trip['name']} (channel: {trip['channel_id']})")
                
        except psycopg2.Error as e:
            print(f"❌ Home Tab query failed: {e}")
            print("This likely means the 'active' column doesn't exist")

def main():
    print("🔍 Debugging Home Tab 'No active trips found' issue...\n")
    
    try:
        has_active_column = check_trips_table_schema()
        check_actual_trips()
        
        if has_active_column:
            check_home_tab_query()
        else:
            print("\n💡 DIAGNOSIS:")
            print("The 'active' column doesn't exist in the trips table.")
            print("The Home Tab is looking for trips WHERE active=TRUE, but this column is missing.")
            print("\nSOLUTION OPTIONS:")
            print("1. Add 'active' column to trips table and set existing trips to active=TRUE")
            print("2. Modify Home Tab query to not filter by active status")
            
    except Exception as e:
        print(f"❌ Error during debugging: {e}")

if __name__ == "__main__":
    main()
