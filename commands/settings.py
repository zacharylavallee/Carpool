"""
Settings commands for the carpool bot
"""
import psycopg2
from config.database import get_conn
from utils.helpers import eph

def register_settings_commands(bolt_app):
    """Register settings commands"""
    
    @bolt_app.command("/settripchannel")
    def cmd_settripchannel(ack, respond, command):
        ack()
        parts = (command.get("text") or "").split()
        if len(parts) != 2:
            return eph(respond, "Usage: `/settripchannel TripName #channel`")
        trip, channel_mention = parts
        if not channel_mention.startswith("<#") or not channel_mention.endswith(">"):
            return eph(respond, ":x: Please mention a channel like #general")
        announcement_channel_id = channel_mention[2:-1].split("|")[0]
        user = command["user_id"]
        channel_id = command["channel_id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT created_by FROM trips WHERE name=%s AND channel_id=%s", (trip, channel_id))
            row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Trip *{trip}* does not exist in this channel.")
        if row[0] != user:
            return eph(respond, ":x: Only the trip creator can set the announcement channel.")
        
        with get_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO trip_settings(trip, channel_id, announcement_channel_id) VALUES(%s,%s,%s)",
                    (trip, channel_id, announcement_channel_id)
                )
            except psycopg2.errors.UniqueViolation:
                cur.execute(
                    "UPDATE trip_settings SET announcement_channel_id=%s WHERE trip=%s AND channel_id=%s",
                    (announcement_channel_id, trip, channel_id)
                )
            conn.commit()
        eph(respond, f":loudspeaker: Announcements for *{trip}* will be posted to {channel_mention}.")
