"""
Channel access restrictions middleware for the carpool bot.
Only allows usage in private channels and DMs.
"""

def register_channel_restrictions(bolt_app):
    """Register middleware to restrict bot to private channels and DMs only"""
    
    @bolt_app.middleware
    def restrict_to_private_channels(body, next):
        """Only allow bot usage in private channels (groups) and DMs"""
        
        # AGGRESSIVE DEBUG LOGGING - This should show up in logs if middleware is running
        print("="*50)
        print("🚨 MIDDLEWARE TRIGGERED!")
        print(f"📋 Body keys: {list(body.keys())}")
        print(f"🔍 Request type: {body.get('type')}")
        print(f"📝 Command: {body.get('command')}")
        print(f"📍 Channel ID: {body.get('channel_id')}")
        print("="*50)
        
        # Get channel ID - for slash commands, it's directly in body["channel_id"]
        channel_id = body.get("channel_id")
        
        # Debug logging
        print(f"🔍 Middleware check: type={body.get('type')}, channel_id={channel_id}")
        print(f"📝 Raw channel_id from body: {repr(body.get('channel_id'))}")
        
        # Check if this is a button action (block_actions) - these should be allowed through
        # since they're responses to ephemeral messages that were already validated
        # For slash commands, body["type"] might be None, so check for presence of "command" key
        if body.get("type") == "block_actions":
            print("✅ Allowing block_actions through middleware")
            next()
            return
        
        # For slash commands, body["type"] is often None, but "command" key is present
        is_slash_command = body.get("command") is not None
        print(f"📝 Is slash command: {is_slash_command} (command: {body.get('command')})")
        
        if channel_id:
            # Use Slack API to check if channel is public or private
            try:
                from app import bolt_app as app
                
                # Try to get channel info using the Slack API
                channel_info = app.client.conversations_info(channel=channel_id)
                
                if channel_info["ok"]:
                    channel = channel_info["channel"]
                    is_private = channel.get("is_private", False)
                    is_im = channel.get("is_im", False)  # Direct message
                    is_mpim = channel.get("is_mpim", False)  # Multi-person DM
                    channel_name = channel.get("name", "unknown")
                    
                    print(f"📊 Channel info: name='{channel_name}', is_private={is_private}, is_im={is_im}, is_mpim={is_mpim}")
                    
                    # Allow private channels, DMs, and multi-person DMs
                    if is_private or is_im or is_mpim:
                        print(f"✅ Allowing private channel/DM: {channel_name}")
                        next()
                        return
                    else:
                        # This is a public channel - block it
                        print(f"❌ Blocking public channel: {channel_name}")
                        
                        # For slash commands (identified by presence of "command" key), provide an error response
                        if is_slash_command:
                            print("📤 Sending error response for blocked slash command")
                            import json
                            import urllib3
                            
                            response_url = body.get("response_url")
                            if response_url:
                                http = urllib3.PoolManager()
                                error_response = {
                                    "response_type": "ephemeral",
                                    "text": f":x: This bot only works in private channels and DMs to prevent notification spam. Please use this command in a private channel instead of #{channel_name}."
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
                        print("🚫 REQUEST BLOCKED - not calling next()")
                        return
                else:
                    print(f"❌ Failed to get channel info: {channel_info.get('error', 'unknown error')}")
                    # If we can't get channel info, fall back to allowing the request
                    # (better to be permissive than to break functionality)
                    print("⚠️ Falling back to allowing request due to API error")
                    
            except Exception as e:
                print(f"❌ Exception getting channel info: {e}")
                # If there's an exception, fall back to allowing the request
                print("⚠️ Falling back to allowing request due to exception")
        else:
            print("⚠️ No channel_id found, allowing request")
        
        # Allow private channels, DMs, and any other cases
        next()
