"""
Channel Guard - Restrict commands to channels where bot is added
"""

def is_bot_in_channel(channel_id: str) -> bool:
    """Check if the bot is added to the specified channel"""
    from app import bolt_app  # Import here to avoid circular imports
    try:
        # Try to get channel info - this will fail if bot isn't in channel
        result = bolt_app.client.conversations_info(channel=channel_id)
        return result.get("ok", False)
    except Exception as e:
        # If we get channel_not_found or not_in_channel, bot isn't added
        error_str = str(e).lower()
        if any(err in error_str for err in ["channel_not_found", "not_in_channel"]):
            return False
        # For other errors, assume bot is in channel to avoid blocking legitimate usage
        return True

def require_bot_in_channel(respond):
    """Decorator to ensure bot is in channel before executing command"""
    def decorator(func):
        def wrapper(ack, respond, command, *args, **kwargs):
            ack()
            channel_id = command["channel_id"]
            
            if not is_bot_in_channel(channel_id):
                respond(
                    ":warning: This bot must be added to the channel to use carpool commands.\n"
                    "Add me with: `/invite @carpool`",
                    response_type="ephemeral"
                )
                return
            
            # Bot is in channel, proceed with command
            return func(ack, respond, command, *args, **kwargs)
        return wrapper
    return decorator

def check_bot_channel_access(channel_id: str, respond) -> bool:
    """
    Check if bot has access to channel and send error message if not.
    Returns True if bot has access, False otherwise.
    """
    if not is_bot_in_channel(channel_id):
        respond(
            ":warning: This bot must be added to the channel to use carpool commands.\n"
            "Add me with: `/invite @carpool`",
            response_type="ephemeral"
        )
        return False
    return True
