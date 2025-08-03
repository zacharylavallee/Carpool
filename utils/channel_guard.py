"""
Channel Guard - Restrict commands to allowed channels defined in environment variables
"""
import os

def get_allowed_channels():
    """Get list of allowed channel IDs from environment variables"""
    allowed_channels_env = os.getenv("ALLOWED_CHANNELS", "")
    if not allowed_channels_env:
        return []
    
    # Split by comma and strip whitespace
    return [channel.strip() for channel in allowed_channels_env.split(",") if channel.strip()]

def is_channel_allowed(channel_id: str) -> bool:
    """Check if the channel is in the allowed channels list"""
    allowed_channels = get_allowed_channels()
    
    # If no channels are configured, allow all channels (backward compatibility)
    if not allowed_channels:
        return True
    
    return channel_id in allowed_channels

def require_allowed_channel(respond):
    """Decorator to ensure command is used in an allowed channel"""
    def decorator(func):
        def wrapper(ack, respond, command, *args, **kwargs):
            ack()
            channel_id = command["channel_id"]
            
            if not is_channel_allowed(channel_id):
                respond(
                    ":x: This channel is not enabled for carpool commands.\n"
                    "Please contact your administrator to enable this channel for the carpool bot.",
                    response_type="ephemeral"
                )
                return
            
            # Channel is allowed, proceed with command
            return func(ack, respond, command, *args, **kwargs)
        return wrapper
    return decorator

def check_bot_channel_access(channel_id: str, respond) -> bool:
    """
    Check if channel is allowed for bot usage and send error message if not.
    Returns True if channel is allowed, False otherwise.
    """
    if not is_channel_allowed(channel_id):
        respond(
            ":x: This channel is not enabled for carpool commands.\n"
            "Please contact your administrator to enable this channel for the carpool bot.",
            response_type="ephemeral"
        )
        return False
    return True
