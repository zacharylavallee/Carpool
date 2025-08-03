"""
Utility functions and helpers for the carpool bot
"""
import logging
from config.database import get_conn

logger = logging.getLogger(__name__)

def eph(respond, text):
    """Send ephemeral response"""
    respond(text, response_type="ephemeral")

def auto_dismiss_eph(respond, text, button_text="Got it"):
    """Send auto-dismissing ephemeral response with dismiss button"""
    respond({
        "response_type": "ephemeral",
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": button_text},
                        "action_id": "dismiss_message",
                        "style": "primary"
                    }
                ]
            }
        ]
    })

def auto_dismiss_eph_with_actions(respond, text, actions):
    """Send auto-dismissing ephemeral response with custom action buttons"""
    # Add dismiss button to the actions
    dismiss_button = {
        "type": "button",
        "text": {"type": "plain_text", "text": "Dismiss"},
        "action_id": "dismiss_message"
    }
    actions.append(dismiss_button)
    
    respond({
        "response_type": "ephemeral",
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            },
            {
                "type": "actions",
                "elements": actions
            }
        ]
    })

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
    """Get the active trip for a channel. Returns (trip_name, created_by) or None if no active trip exists."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, created_by FROM trips WHERE channel_id=%s AND active=TRUE", (channel_id,))
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
        
        # Get all existing car IDs for this trip in this channel, ordered
        cur.execute(
            "SELECT id FROM cars WHERE trip=%s AND channel_id=%s ORDER BY id",
            (trip, channel_id)
        )
        existing_ids = [row[0] for row in cur.fetchall()]
        
        # Find the first gap or return next sequential ID
        if not existing_ids:
            return 1
        
        # Check for gaps in the sequence
        for i in range(1, max(existing_ids) + 1):
            if i not in existing_ids:
                return i
        
        # No gaps found, return next sequential ID
        return max(existing_ids) + 1

def refresh_home_tab_for_channel_users(channel_id: str):
    """Refresh home tab for all users who might be interested in this channel's data"""
    # This is a simplified implementation - in production we'd want to be more selective
    # For now, we'll skip the actual refresh to avoid circular imports and complexity
    # The home tab will refresh when users open it
    pass

def refresh_home_tab_for_user(user_id: str):
    """Refresh home tab for a specific user"""
    try:
        from commands.home_tab import update_home_tab_for_user
        update_home_tab_for_user(user_id)
    except Exception as e:
        logger.error(f"Error refreshing home tab for user {user_id}: {e}")
