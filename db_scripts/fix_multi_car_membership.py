#!/usr/bin/env python3
"""
Fix multi-car membership bug - clean up users who are in multiple cars
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import get_conn

def fix_multi_car_memberships():
    """Find and fix users who are in multiple cars for the same trip"""
    print("🔍 Checking for users in multiple cars...")
    
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Find users who are in multiple cars for the same trip
        cur.execute("""
            SELECT 
                cm.user_id,
                c.trip,
                c.channel_id,
                COUNT(*) as car_count,
                STRING_AGG(CAST(c.id AS TEXT), ', ') as car_ids,
                STRING_AGG(c.name, ', ') as car_names
            FROM car_members cm
            JOIN cars c ON cm.car_id = c.id
            GROUP BY cm.user_id, c.trip, c.channel_id
            HAVING COUNT(*) > 1
            ORDER BY cm.user_id, c.trip
        """)
        
        multi_car_users = cur.fetchall()
        
        if not multi_car_users:
            print("✅ No multi-car membership issues found!")
            return
        
        print(f"❌ Found {len(multi_car_users)} users in multiple cars:")
        
        for user_id, trip, channel_id, car_count, car_ids, car_names in multi_car_users:
            print(f"  User {user_id} in {car_count} cars on '{trip}': {car_names} (IDs: {car_ids})")
            
            # Get the cars this user is in for this trip
            cur.execute("""
                SELECT c.id, c.name, c.created_by, cm.joined_at
                FROM car_members cm
                JOIN cars c ON cm.car_id = c.id
                WHERE cm.user_id = %s AND c.trip = %s AND c.channel_id = %s
                ORDER BY cm.joined_at ASC
            """, (user_id, trip, channel_id))
            
            user_cars = cur.fetchall()
            
            if len(user_cars) <= 1:
                continue
                
            # Keep the user in the FIRST car they joined (earliest joined_at)
            keep_car = user_cars[0]
            remove_cars = user_cars[1:]
            
            print(f"    Keeping user in: {keep_car[1]} (ID: {keep_car[0]}, joined: {keep_car[3]})")
            
            for car_id, car_name, car_owner, joined_at in remove_cars:
                print(f"    Removing from: {car_name} (ID: {car_id}, joined: {joined_at})")
                cur.execute("DELETE FROM car_members WHERE car_id = %s AND user_id = %s", (car_id, user_id))
        
        conn.commit()
        print(f"✅ Fixed {len(multi_car_users)} multi-car membership issues!")

def validate_fix():
    """Validate that the fix worked"""
    print("\n🔍 Validating fix...")
    
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Check for any remaining multi-car memberships
        cur.execute("""
            SELECT 
                cm.user_id,
                c.trip,
                c.channel_id,
                COUNT(*) as car_count
            FROM car_members cm
            JOIN cars c ON cm.car_id = c.id
            GROUP BY cm.user_id, c.trip, c.channel_id
            HAVING COUNT(*) > 1
        """)
        
        remaining_issues = cur.fetchall()
        
        if remaining_issues:
            print(f"❌ Still have {len(remaining_issues)} multi-car membership issues!")
            for user_id, trip, channel_id, car_count in remaining_issues:
                print(f"  User {user_id} still in {car_count} cars on '{trip}'")
        else:
            print("✅ All multi-car membership issues resolved!")

if __name__ == "__main__":
    print("🚗 Multi-Car Membership Fix Script")
    print("=" * 50)
    
    fix_multi_car_memberships()
    validate_fix()
    
    print("\n✅ Script completed!")
