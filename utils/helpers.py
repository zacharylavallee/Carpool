"""
Utility functions and helpers for the carpool bot
"""
import logging
from config.database import get_conn

logger = logging.getLogger(__name__)

def eph(respond, text):
    """Send ephemeral response"""
    respond(text, response_type="ephemeral")

def get_channel_members(channel_id):
    """Get list of user IDs who are members of the given channel."""
    from app import bolt_app  # Import here to avoid circular imports
    try:
        result = bolt_app.client.conversations_members(channel=channel_id)
        return result["members"]
    except Exception as e:
        logger.error(f"Error getting channel members: {e}")
        return []

def get_active_trip(channel_id: str):
    """Get the active trip for a channel. Returns (trip_name, created_by) or None if no trip exists."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, created_by FROM trips WHERE channel_id=%s", (channel_id,))
        row = cur.fetchone()
        return row if row else None

def post_announce(trip: str, channel_id: str, text: str):
    """Post announcement to trip's announcement channel if configured"""
    from app import bolt_app  # Import here to avoid circular imports
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT announcement_channel_id FROM trip_settings WHERE trip=%s AND channel_id=%s", (trip, channel_id))
        row = cur.fetchone()
        if row:
            bolt_app.client.chat_postMessage(channel=row[0], text=text)

def get_username(user_id: str):
    """Get username for a user ID, with fallback to mention format"""
    from app import bolt_app  # Import here to avoid circular imports
    try:
        user_info = bolt_app.client.users_info(user=user_id)
        return user_info["user"]["name"]
    except Exception:
        return f"<@{user_id}>"
