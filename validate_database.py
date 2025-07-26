#!/usr/bin/env python3
"""
Database Validation Script
Comprehensive check of database schema, constraints, and data integrity
Run this to validate your database is properly configured
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables
load_dotenv()

def get_connection():
    """Get database connection"""
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def validate_database():
    """Run comprehensive database validation"""
    print("🔍 Starting comprehensive database validation...")
    print(f"📅 Validation run at: {datetime.now().isoformat()}")
    print("=" * 60)
    
    validation_results = {
        "timestamp": datetime.now().isoformat(),
        "tables": {},
        "constraints": {},
        "data_integrity": {},
        "relationships": {},
        "issues": [],
        "summary": {}
    }
    
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. Check table existence and structure
        print("📋 Step 1: Validating table structures...")
        expected_tables = ['trips', 'cars', 'car_members']
        
        for table_name in expected_tables:
            print(f"\n🔍 Checking table: {table_name}")
            
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name,))
            table_exists = cur.fetchone()['exists']
            
            if not table_exists:
                validation_results["issues"].append(f"Table {table_name} does not exist")
                print(f"   ❌ Table {table_name} does not exist")
                continue
            
            # Get table structure
            cur.execute("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = %s 
                ORDER BY ordinal_position
            """, (table_name,))
            
            columns = cur.fetchall()
            validation_results["tables"][table_name] = {
                "exists": True,
                "columns": [dict(col) for col in columns]
            }
            
            print(f"   ✅ Table exists with {len(columns)} columns:")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"      - {col['column_name']}: {col['data_type']} {nullable}{default}")
        
        # 2. Check constraints
        print(f"\n📋 Step 2: Validating constraints...")
        
        # Primary keys
        cur.execute("""
            SELECT 
                tc.table_name,
                tc.constraint_name,
                tc.constraint_type,
                string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_name IN ('trips', 'cars', 'car_members')
            GROUP BY tc.table_name, tc.constraint_name, tc.constraint_type
            ORDER BY tc.table_name
        """)
        
        primary_keys = cur.fetchall()
        validation_results["constraints"]["primary_keys"] = [dict(pk) for pk in primary_keys]
        
        print("   🔑 Primary Keys:")
        for pk in primary_keys:
            print(f"      - {pk['table_name']}: {pk['columns']} ({pk['constraint_name']})")
        
        # Foreign keys
        cur.execute("""
            SELECT 
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.delete_rule,
                rc.update_rule
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints AS rc
                ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name IN ('trips', 'cars', 'car_members')
            ORDER BY tc.table_name, tc.constraint_name
        """)
        
        foreign_keys = cur.fetchall()
        validation_results["constraints"]["foreign_keys"] = [dict(fk) for fk in foreign_keys]
        
        print("   🔗 Foreign Keys:")
        for fk in foreign_keys:
            print(f"      - {fk['table_name']}.{fk['column_name']} → {fk['foreign_table_name']}.{fk['foreign_column_name']}")
            print(f"        DELETE: {fk['delete_rule']}, UPDATE: {fk['update_rule']} ({fk['constraint_name']})")
        
        # Unique constraints
        cur.execute("""
            SELECT 
                tc.table_name,
                tc.constraint_name,
                string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'UNIQUE'
                AND tc.table_name IN ('trips', 'cars', 'car_members')
            GROUP BY tc.table_name, tc.constraint_name
            ORDER BY tc.table_name
        """)
        
        unique_constraints = cur.fetchall()
        validation_results["constraints"]["unique_constraints"] = [dict(uc) for uc in unique_constraints]
        
        if unique_constraints:
            print("   🎯 Unique Constraints:")
            for uc in unique_constraints:
                print(f"      - {uc['table_name']}: {uc['columns']} ({uc['constraint_name']})")
        else:
            print("   🎯 No unique constraints found")
        
        # 3. Check data integrity
        print(f"\n📋 Step 3: Validating data integrity...")
        
        # Count records in each table
        for table_name in expected_tables:
            if validation_results["tables"].get(table_name, {}).get("exists"):
                cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                count = cur.fetchone()['count']
                validation_results["data_integrity"][f"{table_name}_count"] = count
                print(f"   📊 {table_name}: {count} records")
        
        # Check for orphaned records
        print("   🔍 Checking for orphaned records...")
        
        # Cars without valid trips (if cars table exists)
        if validation_results["tables"].get("cars", {}).get("exists"):
            cur.execute("""
                SELECT COUNT(*) as count
                FROM cars c
                LEFT JOIN trips t ON c.channel_id = t.channel_id
                WHERE t.channel_id IS NULL
            """)
            orphaned_cars = cur.fetchone()['count']
            validation_results["data_integrity"]["orphaned_cars"] = orphaned_cars
            
            if orphaned_cars > 0:
                validation_results["issues"].append(f"Found {orphaned_cars} cars without valid trips")
                print(f"      ❌ {orphaned_cars} cars without valid trips")
            else:
                print(f"      ✅ No orphaned cars found")
        
        # Car members without valid cars (if car_members table exists)
        if validation_results["tables"].get("car_members", {}).get("exists"):
            cur.execute("""
                SELECT COUNT(*) as count
                FROM car_members cm
                LEFT JOIN cars c ON cm.car_id = c.id
                WHERE c.id IS NULL
            """)
            orphaned_members = cur.fetchone()['count']
            validation_results["data_integrity"]["orphaned_car_members"] = orphaned_members
            
            if orphaned_members > 0:
                validation_results["issues"].append(f"Found {orphaned_members} car members without valid cars")
                print(f"      ❌ {orphaned_members} car members without valid cars")
            else:
                print(f"      ✅ No orphaned car members found")
        
        # 4. Check relationships and business logic
        print(f"\n📋 Step 4: Validating business logic...")
        
        # Check for duplicate trips per channel
        if validation_results["tables"].get("trips", {}).get("exists"):
            cur.execute("""
                SELECT channel_id, COUNT(*) as count
                FROM trips
                GROUP BY channel_id
                HAVING COUNT(*) > 1
            """)
            duplicate_trips = cur.fetchall()
            
            if duplicate_trips:
                validation_results["issues"].append(f"Found duplicate trips in channels: {[d['channel_id'] for d in duplicate_trips]}")
                print(f"      ❌ Duplicate trips found in channels:")
                for dup in duplicate_trips:
                    print(f"         - Channel {dup['channel_id']}: {dup['count']} trips")
            else:
                print(f"      ✅ No duplicate trips per channel")
        
        # Check car capacity vs members
        if (validation_results["tables"].get("cars", {}).get("exists") and 
            validation_results["tables"].get("car_members", {}).get("exists")):
            cur.execute("""
                SELECT 
                    c.id,
                    c.name,
                    c.seats,
                    COUNT(cm.user_id) as member_count
                FROM cars c
                LEFT JOIN car_members cm ON c.id = cm.car_id
                GROUP BY c.id, c.name, c.seats
                HAVING COUNT(cm.user_id) > c.seats
            """)
            overcapacity_cars = cur.fetchall()
            
            if overcapacity_cars:
                validation_results["issues"].append(f"Found cars over capacity: {[c['name'] for c in overcapacity_cars]}")
                print(f"      ❌ Cars over capacity:")
                for car in overcapacity_cars:
                    print(f"         - {car['name']}: {car['member_count']}/{car['seats']} members")
            else:
                print(f"      ✅ No cars over capacity")
        
        # 5. Check sequences
        print(f"\n📋 Step 5: Validating sequences...")
        
        cur.execute("""
            SELECT schemaname, sequencename, last_value, increment_by
            FROM pg_sequences
            WHERE schemaname = 'public'
        """)
        sequences = cur.fetchall()
        validation_results["constraints"]["sequences"] = [dict(seq) for seq in sequences]
        
        if sequences:
            print("   🔢 Sequences:")
            for seq in sequences:
                print(f"      - {seq['sequencename']}: last_value={seq['last_value']}, increment={seq['increment_by']}")
        else:
            print("   🔢 No sequences found")
        
        # 6. Generate summary
        print(f"\n📋 Step 6: Generating summary...")
        
        total_issues = len(validation_results["issues"])
        validation_results["summary"] = {
            "total_issues": total_issues,
            "status": "PASS" if total_issues == 0 else "FAIL",
            "tables_validated": len([t for t in validation_results["tables"].values() if t.get("exists")]),
            "total_records": sum([v for k, v in validation_results["data_integrity"].items() if k.endswith("_count")])
        }
        
        print("=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Status: {'✅ PASS' if total_issues == 0 else '❌ FAIL'}")
        print(f"Tables validated: {validation_results['summary']['tables_validated']}")
        print(f"Total records: {validation_results['summary']['total_records']}")
        print(f"Issues found: {total_issues}")
        
        if validation_results["issues"]:
            print("\n❌ Issues found:")
            for issue in validation_results["issues"]:
                print(f"   - {issue}")
        else:
            print("\n✅ No issues found - database is properly configured!")
        
        # Save detailed results to file
        with open('database_validation_results.json', 'w') as f:
            json.dump(validation_results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: database_validation_results.json")
        
        return validation_results

if __name__ == "__main__":
    try:
        results = validate_database()
        exit_code = 0 if results["summary"]["status"] == "PASS" else 1
        exit(exit_code)
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        exit(1)
