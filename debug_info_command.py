#!/usr/bin/env python3
"""
Debug script to check what trips exist in the database and why /info might not be showing them all
"""

import psycopg2
import psycopg2.extras
from config.database import get_conn

def debug_info_command():
    print("🔍 Debugging /info command...")
    
    # You'll need to replace this with the actual channel ID from your Slack channel
    # You can get this from the Slack channel URL or by running a command and checking the logs
    channel_id = input("Enter the channel ID where you ran /info (e.g., C097MRL9RU4): ").strip()
    
    if not channel_id:
        print("❌ Channel ID is required")
        return
    
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        print(f"\n📋 Checking trips for channel: {channel_id}")
        print("=" * 60)
        
        # Get all trips in this channel
        cur.execute(
            "SELECT name, created_by, created_at FROM trips WHERE channel_id=%s ORDER BY created_at DESC",
            (channel_id,)
        )
        all_trips = cur.fetchall()
        
        print(f"📊 Found {len(all_trips)} trip(s):")
        
        if not all_trips:
            print("❌ No trips found in this channel")
            return
        
        for i, trip in enumerate(all_trips):
            status = " (ACTIVE)" if i == 0 else " (inactive)"
            print(f"  {i+1}. '{trip['name']}' by {trip['created_by']} at {trip['created_at']}{status}")
        
        print("\n🔍 Checking what /info logic would do:")
        print("=" * 60)
        
        active_trip = all_trips[0]['name']
        print(f"Active trip: {active_trip}")
        
        if len(all_trips) == 1:
            print("✅ Logic: Single trip mode - would show 'Active Trip: ...'")
        else:
            print("✅ Logic: Multiple trips mode - would show 'All Trips in this Channel:'")
            print("Expected output:")
            print(":round_pushpin: **All Trips in this Channel:**")
            for i, trip in enumerate(all_trips):
                status = " (active)" if i == 0 else ""
                print(f"• *{trip['name']}* by <@{trip['created_by']}>{status}")
        
        # Check cars for active trip
        print(f"\n🚗 Checking cars for active trip '{active_trip}':")
        cur.execute(
            """
            SELECT c.id, c.name, c.seats, ARRAY_AGG(m.user_id) AS members
            FROM cars c
            LEFT JOIN car_members m ON m.car_id=c.id
            WHERE c.trip=%s AND c.channel_id=%s
            GROUP BY c.id, c.name, c.seats
            ORDER BY c.id
            """, (active_trip, channel_id)
        )
        cars = cur.fetchall()
        
        print(f"📊 Found {len(cars)} car(s) on active trip:")
        if cars:
            for c in cars:
                members = [m for m in c['members'] if m is not None]
                print(f"  • Car {c['id']}: {c['name']} ({len(members)}/{c['seats']} seats)")
        else:
            print("  No cars found")

if __name__ == "__main__":
    debug_info_command()
