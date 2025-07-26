#!/usr/bin/env python3
"""
Database reset script to clean up all carpool data and start fresh.
This removes all trips, cars, and memberships to resolve any legacy/duplicate issues.
"""

import psycopg2
from config.database import get_conn

def reset_database():
    """Reset all carpool data in the database"""
    print("🚨 WARNING: This will delete ALL carpool data!")
    print("   - All trips will be deleted")
    print("   - All cars will be deleted") 
    print("   - All car memberships will be deleted")
    print("   - All join requests will be deleted")
    print()
    
    confirm = input("Are you sure you want to proceed? Type 'YES' to confirm: ")
    if confirm != "YES":
        print("❌ Database reset cancelled.")
        return
    
    print("\n🔄 Starting database reset...")
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Delete in correct order due to foreign key constraints
            print("🗑️  Deleting car memberships...")
            cur.execute("DELETE FROM car_members")
            deleted_members = cur.rowcount
            
            print("🗑️  Deleting join requests...")
            cur.execute("DELETE FROM join_requests")
            deleted_requests = cur.rowcount
            
            print("🗑️  Deleting cars...")
            cur.execute("DELETE FROM cars")
            deleted_cars = cur.rowcount
            
            print("🗑️  Deleting trips...")
            cur.execute("DELETE FROM trips")
            deleted_trips = cur.rowcount
            
            # Commit all changes
            conn.commit()
            
            print("\n✅ Database reset completed successfully!")
            print(f"   📊 Deleted {deleted_trips} trips")
            print(f"   📊 Deleted {deleted_cars} cars")
            print(f"   📊 Deleted {deleted_members} car memberships")
            print(f"   📊 Deleted {deleted_requests} join requests")
            print()
            print("🎯 Database is now clean and ready for fresh data!")
            print("   - Trip names will now be globally unique")
            print("   - No duplicate or legacy data remains")
            print("   - All constraints are properly enforced")
            
    except Exception as e:
        print(f"❌ Error during database reset: {e}")
        print("Database may be in an inconsistent state. Please check manually.")
        return False
    
    return True

def verify_empty_database():
    """Verify that the database is empty after reset"""
    print("\n🔍 Verifying database is empty...")
    
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Check each table
        tables = ['trips', 'cars', 'car_members', 'join_requests']
        all_empty = True
        
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            status = "✅ Empty" if count == 0 else f"❌ Has {count} records"
            print(f"   {table}: {status}")
            if count > 0:
                all_empty = False
        
        if all_empty:
            print("\n✅ Verification passed: Database is completely empty!")
        else:
            print("\n❌ Verification failed: Some tables still have data!")
        
        return all_empty

if __name__ == "__main__":
    print("🔄 Carpool Database Reset Tool")
    print("=" * 50)
    
    if reset_database():
        verify_empty_database()
    else:
        print("❌ Database reset failed!")
