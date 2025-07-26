#!/usr/bin/env python3
"""
Quick database schema check script
"""

import os
import psycopg2
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

def check_database():
    """Check current database schema"""
    with get_conn() as conn:
        cur = conn.cursor()
        
        print("Checking database schema...")
        
        # Check all tables and their columns
        tables_to_check = ['trips', 'cars', 'car_members', 'join_requests', 'trip_settings']
        
        for table in tables_to_check:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            
            columns = cur.fetchall()
            if columns:
                print(f"\n✅ Table '{table}' exists with columns:")
                for col_name, data_type, nullable in columns:
                    print(f"  - {col_name}: {data_type} ({'NULL' if nullable == 'YES' else 'NOT NULL'})")
            else:
                print(f"\n❌ Table '{table}' does not exist")

if __name__ == "__main__":
    check_database()
