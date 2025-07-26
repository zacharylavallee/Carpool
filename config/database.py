"""
Database configuration and connection utilities
"""
import os
import logging
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv, find_dotenv

# Load environment variables
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
    logging.info(f"Loaded .env from {dotenv_path}")
else:
    logging.warning(".env file not found; relying on environment variables")

# Retrieve database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logging.error("DATABASE_URL is not set. Exiting.")
    exit(1)

def get_conn():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    """Initialize database schema"""
    with get_conn() as conn:
        cur = conn.cursor()
        # Trips
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            name TEXT,
            channel_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(name, channel_id)
        )""")
        # Cars
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY,
            trip TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            name TEXT NOT NULL,
            seats INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(trip, channel_id) REFERENCES trips(name, channel_id) ON DELETE CASCADE,
            UNIQUE(trip, channel_id, created_by)
        )""")
        # Memberships
        cur.execute("""
        CREATE TABLE IF NOT EXISTS car_members (
            car_id INTEGER REFERENCES cars(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(car_id, user_id)
        )""")
        # Join requests
        cur.execute("""
        CREATE TABLE IF NOT EXISTS join_requests (
            car_id INTEGER REFERENCES cars(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(car_id, user_id)
        )""")

        conn.commit()
