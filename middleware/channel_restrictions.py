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
        
        # Debug logging
        print(f"🔍 Middleware check: type={body.get('type')}, channel_id={channel_id}")
        
        # Check if this is a button action (block_actions) - these should be allowed through
        # since they're responses to ephemeral messages that were already validated
        if body.get("type") == "block_actions":
            print("✅ Allowing block_actions through middleware")
            next()
            return
        
        if channel_id:
            # Channel ID patterns:
            # C* = Public channels (block these)
            # G* = Private channels (allow)
            # D* = Direct messages (allow)
            # U* = User IDs in DMs (allow)
            
            if channel_id.startswith("C"):
                print(f"❌ Blocking public channel: {channel_id}")
                # This is a public channel - block it
                # For slash commands, provide an error response
                if body.get("type") == "slash_command":
                    print("📤 Sending error response for blocked slash command")
                    # We need to respond immediately to prevent the command from proceeding
                    import json
                    import urllib3
                    
                    response_url = body.get("response_url")
                    if response_url:
                        http = urllib3.PoolManager()
                        error_response = {
                            "response_type": "ephemeral",
                            "text": ":x: This bot only works in private channels and DMs to prevent notification spam. Please use this command in a private channel."
                        }
                        try:
                            http.request(
                                'POST',
                                response_url,
                                body=json.dumps(error_response),
                                headers={'Content-Type': 'application/json'}
                            )
                            print("✅ Error response sent successfully")
                        except Exception as e:
                            print(f"❌ Failed to send error response: {e}")
                    else:
                        print("❌ No response_url found in body")
                # Don't call next() - this blocks the request
                return
            else:
                print(f"✅ Allowing private channel/DM: {channel_id}")
        else:
            print("⚠️ No channel_id found, allowing request")
        
        # Allow private channels, DMs, and any other cases
        next()
