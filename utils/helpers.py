"""
Utility functions and helpers for the carpool bot
"""
import logging
from config.database import get_conn

logger = logging.getLogger(__name__)

def eph(respond, text):
    """Send ephemeral response"""
    respond(text, response_type="ephemeral")

def get_channel_members(channel_id: str):
    """Get all human members of a channel (excluding bots)"""
    from app import bolt_app  # Import here to avoid circular imports
    try:
        # First check if we have the right permissions
        result = bolt_app.client.conversations_members(channel=channel_id)
        members = result["members"]
        
        # Get bot's own user ID to exclude it
        try:
            bot_info = bolt_app.client.auth_test()
            bot_user_id = bot_info["user_id"]
        except Exception as e:
            logger.error(f"Error getting bot user ID: {e}")
            bot_user_id = None
        
        # Filter out bot users and the bot itself
        human_members = []
        for member_id in members:
            # Skip if this is the bot's own user ID
            if bot_user_id and member_id == bot_user_id:
                continue
                
            try:
                user_info = bolt_app.client.users_info(user=member_id)
                if not user_info["user"].get("is_bot", False):
                    human_members.append(member_id)
            except Exception as e:
                logger.error(f"Error getting user info for {member_id}: {e}")
                # If we can't get user info, assume it's human to be safe
                # But still exclude if it matches the bot user ID
                if not (bot_user_id and member_id == bot_user_id):
                    human_members.append(member_id)
        
        return human_members
    except Exception as e:
        logger.error(f"Error getting channel members for {channel_id}: {e}")
        # Check if it's a permissions error
        if "missing_scope" in str(e) or "not_in_channel" in str(e):
            logger.error(f"Permissions issue: {e}")
        return []

def get_active_trip(channel_id: str):
    """Get the active trip for a channel. Returns (trip_name, created_by) or None if no trip exists."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, created_by FROM trips WHERE channel_id=%s", (channel_id,))
        row = cur.fetchone()
        return row if row else None

def post_announce(trip: str, channel_id: str, text: str):
    """Post announcement to the trip's channel"""
    from app import bolt_app  # Import here to avoid circular imports
    bolt_app.client.chat_postMessage(channel=channel_id, text=text)

def get_username(user_id: str):
    """Get username for a user ID, with fallback to mention format"""
    from app import bolt_app  # Import here to avoid circular imports
    try:
        user_info = bolt_app.client.users_info(user=user_id)
        return user_info["user"]["name"]
    except Exception:
        return f"<@{user_id}>"

def get_next_available_car_id(trip: str, channel_id: str):
    """Find the next available car ID globally, reusing deleted IDs when possible"""
    with get_conn() as conn:
        cur = conn.cursor()
        # Get all existing car IDs across ALL trips, ordered
        cur.execute("SELECT id FROM cars ORDER BY id")
        existing_ids = [row[0] for row in cur.fetchall()]
        
        # Find the first gap in the sequence, starting from 1
        next_id = 1
        for existing_id in existing_ids:
            if existing_id == next_id:
                next_id += 1
            elif existing_id > next_id:
                # Found a gap, use the current next_id
                break
        
        return next_id
