#!/usr/bin/env python3
"""
Temporary diagnostic script to investigate trip visibility issues
This script will be deleted after diagnosis
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

def check_channel_status(channel_id):
    """Check if a channel is still active via Slack API"""
    try:
        import requests
        import json
        
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            return "❓ No bot token"
        
        headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"https://slack.com/api/conversations.info?channel={channel_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                channel = data.get("channel", {})
                is_archived = channel.get("is_archived", False)
                return "❌ Archived" if is_archived else "✅ Active"
            else:
                error = data.get("error", "unknown")
                return f"❌ Error: {error}"
        else:
            return f"❌ HTTP {response.status_code}"
    except Exception as e:
        return f"❓ Exception: {str(e)[:50]}"

def diagnose_trips():
    """Diagnose trip visibility and database state"""
    print("🔍 TRIP DIAGNOSTIC REPORT")
    print("=" * 60)
    print(f"📅 Generated at: {datetime.now().isoformat()}")
    print()
    
    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Get ALL trips with detailed information
            print("📋 QUERYING ALL TRIPS...")
            cur.execute("""
                SELECT 
                    name, 
                    created_by, 
                    created_at, 
                    channel_id,
                    (SELECT COUNT(*) FROM cars WHERE trip = trips.name) as car_count,
                    (SELECT COUNT(*) FROM car_members cm 
                     JOIN cars c ON cm.car_id = c.id 
                     WHERE c.trip = trips.name) as member_count
                FROM trips 
                ORDER BY created_at DESC
            """)
            all_trips = cur.fetchall()
            
            if not all_trips:
                print("❌ NO TRIPS FOUND IN DATABASE")
                return
            
            print(f"✅ Found {len(all_trips)} trip(s) in database")
            print()
            
            print("🚗 TRIP DETAILS:")
            print("-" * 60)
            
            for i, trip in enumerate(all_trips, 1):
                channel_status = check_channel_status(trip['channel_id'])
                
                print(f"{i}. TRIP: {trip['name']}")
                print(f"   📍 Channel: {trip['channel_id']} ({channel_status})")
                print(f"   👤 Creator: {trip['created_by']}")
                print(f"   📅 Created: {trip['created_at']}")
                print(f"   🚗 Cars: {trip['car_count']}")
                print(f"   👥 Members: {trip['member_count']}")
                print()
            
            # Look for any trips that might have been cleaned up
            print("🔍 CHECKING FOR RECENT DELETIONS...")
            
            # Check if there are any orphaned cars (shouldn't exist due to constraints)
            cur.execute("""
                SELECT c.*, 'ORPHANED_CAR' as issue_type
                FROM cars c
                LEFT JOIN trips t ON c.trip = t.name
                WHERE t.name IS NULL
            """)
            orphaned_cars = cur.fetchall()
            
            if orphaned_cars:
                print(f"⚠️  Found {len(orphaned_cars)} orphaned cars:")
                for car in orphaned_cars:
                    print(f"   - Car ID {car['id']}: {car['name']} (trip: {car['trip']})")
            else:
                print("✅ No orphaned cars found")
            
            # Check for orphaned car members
            cur.execute("""
                SELECT cm.*, 'ORPHANED_MEMBER' as issue_type
                FROM car_members cm
                LEFT JOIN cars c ON cm.car_id = c.id
                WHERE c.id IS NULL
            """)
            orphaned_members = cur.fetchall()
            
            if orphaned_members:
                print(f"⚠️  Found {len(orphaned_members)} orphaned members:")
                for member in orphaned_members:
                    print(f"   - User {member['user_id']} in non-existent car {member['car_id']}")
            else:
                print("✅ No orphaned members found")
            
            print()
            print("🎯 SUMMARY:")
            print(f"   • Total trips: {len(all_trips)}")
            print(f"   • Active channels: {sum(1 for trip in all_trips if check_channel_status(trip['channel_id']).startswith('✅'))}")
            print(f"   • Archived channels: {sum(1 for trip in all_trips if 'Archived' in check_channel_status(trip['channel_id']))}")
            print(f"   • Error channels: {sum(1 for trip in all_trips if 'Error' in check_channel_status(trip['channel_id']) or 'Exception' in check_channel_status(trip['channel_id']))}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_trips()
