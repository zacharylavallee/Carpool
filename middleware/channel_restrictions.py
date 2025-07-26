"""
Channel access restrictions middleware for the carpool bot.
Only allows usage in private channels and DMs.
"""

def register_channel_restrictions(bolt_app):
    """Register middleware to restrict bot to private channels and DMs only"""
    
    @bolt_app.middleware
    def restrict_to_private_channels(body, next):
        """Only allow bot usage in private channels (groups) and DMs"""
        
        # Get channel ID from various possible locations
        channel_id = (
            body.get("channel_id") or 
            body.get("event", {}).get("channel") or
            body.get("channel", {}).get("id") if isinstance(body.get("channel"), dict) else body.get("channel")
        )
        
        if channel_id:
            # Channel ID patterns:
            # C* = Public channels (block these)
            # G* = Private channels (allow)
            # D* = Direct messages (allow)
            # U* = User IDs in DMs (allow)
            
            if channel_id.startswith("C"):
                # This is a public channel - block it
                return
        
        # Allow private channels, DMs, and any other cases
        next()
