#!/usr/bin/env python3
"""
Debug Bot Issue Script
Diagnose the current database state and identify bot runtime issues
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

def debug_bot_issue():
    """Debug the current bot issue"""
    print("🔍 Debugging bot runtime issue...")
    print(f"📅 Debug run at: {datetime.now().isoformat()}")
    print("=" * 60)
    
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("📋 Step 1: Current database state...")
        
        # Check trips
        cur.execute("SELECT * FROM trips ORDER BY created_at DESC")
        trips = cur.fetchall()
        print(f"🚗 Trips ({len(trips)}):")
        for trip in trips:
            print(f"   - {trip['name']} (channel: {trip['channel_id']}, created by: {trip['created_by']})")
        
        # Check cars
        cur.execute("SELECT * FROM cars ORDER BY created_at DESC")
        cars = cur.fetchall()
        print(f"\n🚙 Cars ({len(cars)}):")
        for car in cars:
            print(f"   - Car {car['id']}: {car['name']} ({car['seats']} seats)")
            print(f"     Trip: {car['trip']}, Channel: {car['channel_id']}")
            print(f"     Created by: {car['created_by']}")
        
        # Check car members
        cur.execute("SELECT * FROM car_members ORDER BY joined_at DESC")
        members = cur.fetchall()
        print(f"\n👥 Car Members ({len(members)}):")
        for member in members:
            print(f"   - User {member['user_id']} in car {member['car_id']}")
        
        # Check join requests
        cur.execute("SELECT * FROM join_requests ORDER BY requested_at DESC")
        requests = cur.fetchall()
        print(f"\n📝 Join Requests ({len(requests)}):")
        for request in requests:
            print(f"   - User {request['user_id']} requesting car {request['car_id']}")
        
        print("\n📋 Step 2: Analyzing the issue...")
        
        # Look for potential issues
        issues = []
        
        # Check for orphaned cars (cars without valid trips)
        cur.execute("""
            SELECT c.*, t.name as trip_name
            FROM cars c
            LEFT JOIN trips t ON c.channel_id = t.channel_id AND c.trip = t.name
            WHERE t.name IS NULL
        """)
        orphaned_cars = cur.fetchall()
        if orphaned_cars:
            issues.append(f"Found {len(orphaned_cars)} orphaned cars (cars without valid trips)")
            for car in orphaned_cars:
                print(f"   ⚠️  Orphaned car {car['id']}: {car['name']} (trip: {car['trip']}, channel: {car['channel_id']})")
        
        # Check for duplicate cars by same user in same trip
        cur.execute("""
            SELECT channel_id, trip, created_by, COUNT(*) as car_count
            FROM cars
            GROUP BY channel_id, trip, created_by
            HAVING COUNT(*) > 1
        """)
        duplicate_cars = cur.fetchall()
        if duplicate_cars:
            issues.append(f"Found {len(duplicate_cars)} users with multiple cars in same trip")
            for dup in duplicate_cars:
                print(f"   ⚠️  User {dup['created_by']} has {dup['car_count']} cars in {dup['trip']} (channel: {dup['channel_id']})")
        
        # Check for cars with invalid user IDs (might indicate Slack API issues)
        cur.execute("SELECT DISTINCT created_by FROM cars")
        car_creators = [row['created_by'] for row in cur.fetchall()]
        
        cur.execute("SELECT DISTINCT created_by FROM trips")
        trip_creators = [row['created_by'] for row in cur.fetchall()]
        
        all_users = set(car_creators + trip_creators)
        print(f"\n👤 User IDs found in database:")
        for user_id in all_users:
            print(f"   - {user_id}")
            # Check if this looks like a valid Slack user ID (should start with U)
            if not user_id.startswith('U'):
                issues.append(f"Invalid user ID format: {user_id} (should start with 'U')")
        
        print(f"\n📋 Step 3: Issue summary...")
        
        if issues:
            print(f"❌ Found {len(issues)} potential issues:")
            for i, issue in enumerate(issues, 1):
                print(f"   {i}. {issue}")
        else:
            print("✅ No obvious database issues found")
        
        print(f"\n📋 Step 4: Recommendations...")
        
        # Provide specific recommendations
        if orphaned_cars:
            print("🔧 To fix orphaned cars:")
            print("   - Delete orphaned cars or recreate matching trips")
        
        if duplicate_cars:
            print("🔧 To fix duplicate cars:")
            print("   - Remove extra cars keeping only the most recent one")
        
        if any(not uid.startswith('U') for uid in all_users):
            print("🔧 To fix invalid user IDs:")
            print("   - Check Slack bot token permissions")
            print("   - Verify bot can access user information")
            print("   - Test with a valid Slack workspace")
        
        print("\n💡 Common causes of 'Could not retrieve channel members':")
        print("   - Bot missing 'channels:read' or 'users:read' permissions")
        print("   - Bot not added to the channel")
        print("   - Invalid or expired bot token")
        print("   - Testing in DM instead of channel")
        
        print("\n💡 Common causes of 'You already created a car':")
        print("   - Previous test data still in database")
        print("   - User ID mismatch between tests")
        print("   - Orphaned car records")
        
        return issues

if __name__ == "__main__":
    try:
        issues = debug_bot_issue()
        print(f"\n🎯 Debug complete. Found {len(issues)} issues to investigate.")
        exit(0)
    except Exception as e:
        print(f"❌ Debug failed with error: {e}")
        exit(1)
