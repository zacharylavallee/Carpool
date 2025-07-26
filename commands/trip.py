"""
Trip management commands for the carpool bot
"""
import psycopg2
from config.database import get_conn
from utils.helpers import eph

def register_trip_commands(bolt_app):
    """Register trip management commands"""
    
    @bolt_app.command("/createtrip")
    def cmd_createtrip(ack, respond, command):
        ack()
        trip = (command.get("text") or "").strip()
        if not trip:
            return eph(respond, "Usage: `/createtrip TripName`")
        user = command["user_id"]
        channel_id = command["channel_id"]
        with get_conn() as conn:
            cur = conn.cursor()
            try:
                # Try to insert new trip (will fail if channel already has a trip)
                cur.execute(
                    "INSERT INTO trips(name, channel_id, created_by) VALUES(%s,%s,%s)",
                    (trip, channel_id, user)
                )
                conn.commit()
                eph(respond, f":round_pushpin: Trip *{trip}* created for this channel.")
            except psycopg2.errors.UniqueViolation:
                # Channel already has a trip, update it instead
                cur.execute(
                    "UPDATE trips SET name=%s, created_by=%s, created_at=CURRENT_TIMESTAMP WHERE channel_id=%s",
                    (trip, user, channel_id)
                )
                conn.commit()
                eph(respond, f":round_pushpin: Trip *{trip}* replaced the existing trip for this channel.")

    @bolt_app.command("/deletetrip")
    def cmd_deletetrip(ack, respond, command):
        ack()
        user = command["user_id"]
        channel_id = command["channel_id"]
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name, created_by FROM trips WHERE channel_id=%s", (channel_id,))
            row = cur.fetchone()
        if not row:
            return eph(respond, ":x: No trip exists in this channel.")
        trip_name, creator = row
        if creator != user:
            return eph(respond, ":x: Only the trip creator can delete it.")
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM trips WHERE channel_id=%s", (channel_id,))
            conn.commit()
            eph(respond, f":wastebasket: Trip *{trip_name}* deleted from this channel.")
