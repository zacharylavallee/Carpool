#!/usr/bin/env python3
"""
Database migration script to ensure production database has correct schema.
This script will add missing columns and tables safely.
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

def migrate_database():
    """Apply database migrations safely"""
    with get_conn() as conn:
        cur = conn.cursor()
        
        print("Starting database migration...")
        
        # Check if trips table exists and has channel_id column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trips' AND column_name = 'channel_id'
        """)
        if not cur.fetchone():
            print("Adding channel_id column to trips table...")
            try:
                cur.execute("ALTER TABLE trips ADD COLUMN channel_id TEXT NOT NULL DEFAULT ''")
                conn.commit()
                print("✅ Added channel_id to trips table")
            except psycopg2.Error as e:
                print(f"⚠️  Error adding channel_id to trips: {e}")
                conn.rollback()
        else:
            print("✅ trips.channel_id already exists")
            
        # Check if cars table exists and has channel_id column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'cars' AND column_name = 'channel_id'
        """)
        if not cur.fetchone():
            print("Adding channel_id column to cars table...")
            try:
                cur.execute("ALTER TABLE cars ADD COLUMN channel_id TEXT NOT NULL DEFAULT ''")
                conn.commit()
                print("✅ Added channel_id to cars table")
            except psycopg2.Error as e:
                print(f"⚠️  Error adding channel_id to cars: {e}")
                conn.rollback()
        else:
            print("✅ cars.channel_id already exists")
            
        # Ensure all tables exist with correct schema
        print("Ensuring all tables exist with correct schema...")
        
        # Trips table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            name TEXT,
            channel_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(name, channel_id)
        )""")
        
        # Cars table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id SERIAL PRIMARY KEY,
            trip TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            name TEXT NOT NULL,
            seats INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(trip, channel_id) REFERENCES trips(name, channel_id) ON DELETE CASCADE,
            UNIQUE(trip, channel_id, created_by)
        )""")
        
        # Car members table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS car_members (
            car_id INTEGER REFERENCES cars(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(car_id, user_id)
        )""")
        
        # Join requests table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS join_requests (
            car_id INTEGER REFERENCES cars(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(car_id, user_id)
        )""")
        
        # Trip settings table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trip_settings (
            trip TEXT,
            channel_id TEXT,
            announcement_channel_id TEXT NOT NULL,
            PRIMARY KEY(trip, channel_id),
            FOREIGN KEY(trip, channel_id) REFERENCES trips(name, channel_id) ON DELETE CASCADE
        )""")
        
        conn.commit()
        print("✅ All tables created/verified successfully")
        
        print("Database migration completed successfully!")

if __name__ == "__main__":
    migrate_database()
