# database.py
import sqlite3
from typing import List, Dict, Any

DB_PATH = "carpool_app.db"

def init_db():
    """(Re)create tables, wiping any old test data."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # Drop old tables
        c.execute("DROP TABLE IF EXISTS car_members")
        c.execute("DROP TABLE IF EXISTS cars")
        c.execute("DROP TABLE IF EXISTS team_settings")
        c.execute("DROP TABLE IF EXISTS installations")
        c.execute("DROP TABLE IF EXISTS join_requests")

        # Installations (for OAuth)
        c.execute("""
            CREATE TABLE installations (
                team_id TEXT PRIMARY KEY,
                bot_token TEXT NOT NULL,
                signing_secret TEXT NOT NULL,
                scope TEXT,
                installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Cars: id is PRIMARY KEY but no AUTOINCREMENT
        c.execute("""
            CREATE TABLE cars (
                id INTEGER PRIMARY KEY,
                team_id TEXT NOT NULL,
                name TEXT NOT NULL,
                seats INTEGER NOT NULL,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Who's in each car
        c.execute("""
            CREATE TABLE car_members (
                car_id INTEGER,
                user_id TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(car_id, user_id)
            )
        """)

        # Pending join requests
        c.execute("""
            CREATE TABLE join_requests (
                car_id INTEGER,
                user_id TEXT,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(car_id, user_id)
            )
        """)

        # Per-team settings
        c.execute("""
            CREATE TABLE team_settings (
                team_id TEXT PRIMARY KEY,
                channel_id TEXT
            )
        """)
        conn.commit()

def _next_id_for_team(team_id: str) -> int:
    """Find smallest unused positive ID for this team."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM cars WHERE team_id = ? ORDER BY id", (team_id,))
        used = [row[0] for row in c.fetchall()]
    nxt = 1
    for u in used:
        if u == nxt:
            nxt += 1
        elif u > nxt:
            break
    return nxt

def create_car(team_id: str, name: str, seats: int, created_by: str) -> int:
    """Insert a new car with the smallest available ID."""
    car_id = _next_id_for_team(team_id)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO cars(id, team_id, name, seats, created_by) VALUES (?, ?, ?, ?, ?)",
            (car_id, team_id, name, seats, created_by)
        )
        conn.commit()
    return car_id

def list_cars(team_id: str) -> List[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, name, seats, created_by, created_at FROM cars WHERE team_id = ?",
            (team_id,)
        )
        cols = [col[0] for col in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]

def join_car(team_id: str, car_id: int, user_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM cars WHERE id = ? AND team_id = ?", (car_id, team_id))
        if not c.fetchone():
            return False
        c.execute(
            "INSERT OR IGNORE INTO car_members(car_id, user_id) VALUES (?, ?)",
            (car_id, user_id)
        )
        conn.commit()
    return True

def get_car_members(car_id: int) -> List[str]:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM car_members WHERE car_id = ?", (car_id,))
        return [row[0] for row in c.fetchall()]

