#!/usr/bin/env python3
"""
Test script to verify public channel blocking works
"""

import json
from app import bolt_app

def simulate_slash_command_in_public_channel():
    """Simulate a slash command in a public channel to test blocking"""
    
    # Simulate the body of a slash command in a public channel
    test_body = {
        "type": "slash_command",
        "channel_id": "C09870D81DE",  # all-znltest (public channel from your test)
        "response_url": "https://hooks.slack.com/commands/test",
        "command": "/trip",
        "text": "testtrip"
    }
    
    print("🧪 Testing middleware with simulated public channel slash command...")
    print(f"📍 Channel ID: {test_body['channel_id']}")
    
    # This would normally be called by the middleware
    try:
        # Get channel info like the middleware does
        channel_info = bolt_app.client.conversations_info(channel=test_body['channel_id'])
        
        if channel_info["ok"]:
            channel = channel_info["channel"]
            is_private = channel.get("is_private", False)
            is_im = channel.get("is_im", False)
            is_mpim = channel.get("is_mpim", False)
            channel_name = channel.get("name", "unknown")
            
            print(f"📊 Channel info: name='{channel_name}', is_private={is_private}, is_im={is_im}, is_mpim={is_mpim}")
            
            if is_private or is_im or is_mpim:
                print("✅ Would be ALLOWED (private/DM)")
                return True
            else:
                print("❌ Would be BLOCKED (public)")
                print("📤 Would send error response to user")
                return False
        else:
            print(f"❌ Failed to get channel info: {channel_info.get('error', 'unknown error')}")
            return True  # Fallback to allow
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return True  # Fallback to allow

if __name__ == "__main__":
    result = simulate_slash_command_in_public_channel()
    print(f"\n🎯 Final result: {'BLOCKED' if not result else 'ALLOWED'}")
