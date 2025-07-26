#!/usr/bin/env python3
"""
Check Database Constraints
Quick script to check what constraints are on the cars table
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_constraints():
    """Check constraints on cars table"""
    print("🔍 Checking cars table constraints...")
    
    with psycopg2.connect(os.getenv("DATABASE_URL")) as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check table structure
        print("\n📊 Cars table structure:")
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'cars' 
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
            print(f"   - {col['column_name']}: {col['data_type']} {nullable}{default}")
        
        # Check constraints
        print("\n🔒 Table constraints:")
        cur.execute("""
            SELECT 
                tc.constraint_name,
                tc.constraint_type,
                string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'cars'
            GROUP BY tc.constraint_name, tc.constraint_type
            ORDER BY tc.constraint_type, tc.constraint_name
        """)
        constraints = cur.fetchall()
        for constraint in constraints:
            print(f"   - {constraint['constraint_type']}: {constraint['constraint_name']} ({constraint['columns']})")
        
        # Check unique constraints specifically
        print("\n🔑 Unique constraints details:")
        cur.execute("""
            SELECT 
                tc.constraint_name,
                string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'cars' AND tc.constraint_type = 'UNIQUE'
            GROUP BY tc.constraint_name
        """)
        unique_constraints = cur.fetchall()
        for uc in unique_constraints:
            print(f"   - UNIQUE on: {uc['columns']}")
        
        print("\n🎯 Analysis:")
        print("This will show us exactly what constraint is preventing car creation.")

if __name__ == "__main__":
    check_constraints()
