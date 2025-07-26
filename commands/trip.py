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
            # Delete any existing trip for this channel (one trip per channel)
            cur.execute("DELETE FROM trips WHERE channel_id=%s", (channel_id,))
            # Create the new trip
            cur.execute(
                "INSERT INTO trips(name, channel_id, created_by) VALUES(%s,%s,%s)",
                (trip, channel_id, user)
            )
            conn.commit()
            eph(respond, f":round_pushpin: Trip *{trip}* created for this channel.")

    @bolt_app.command("/deletetrip")
    def cmd_deletetrip(ack, respond, command):
        ack()
        trip = (command.get("text") or "").strip()
        if not trip:
            return eph(respond, "Usage: `/deletetrip TripName`")
        user = command["user_id"]
        channel_id = command["channel_id"]
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT created_by FROM trips WHERE name=%s AND channel_id=%s", (trip, channel_id))
            row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Trip *{trip}* does not exist in this channel.")
        if row[0] != user:
            return eph(respond, ":x: Only the trip creator can delete it.")
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM trips WHERE name=%s AND channel_id=%s", (trip, channel_id))
            conn.commit()
        eph(respond, f":wastebasket: Trip *{trip}* deleted.")
