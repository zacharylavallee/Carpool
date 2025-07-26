#!/usr/bin/env python3
"""
Test script to verify channel detection is working
"""

from app import bolt_app

def test_channel_info(channel_id):
    """Test getting channel info for a specific channel"""
    try:
        print(f"🔍 Testing channel: {channel_id}")
        
        # Get channel info using the Slack API
        channel_info = bolt_app.client.conversations_info(channel=channel_id)
        
        if channel_info["ok"]:
            channel = channel_info["channel"]
            is_private = channel.get("is_private", False)
            is_im = channel.get("is_im", False)
            is_mpim = channel.get("is_mpim", False)
            channel_name = channel.get("name", "unknown")
            
            print(f"📊 Channel info:")
            print(f"   Name: {channel_name}")
            print(f"   Is Private: {is_private}")
            print(f"   Is IM: {is_im}")
            print(f"   Is MPIM: {is_mpim}")
            
            # Determine if this would be blocked
            if is_private or is_im or is_mpim:
                print("✅ Would be ALLOWED (private/DM)")
            else:
                print("❌ Would be BLOCKED (public)")
                
        else:
            print(f"❌ Failed to get channel info: {channel_info.get('error', 'unknown error')}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    # Test with the channel where you created the trip
    # Replace with the actual channel ID
    test_channel_id = input("Enter the channel ID where you created the trip: ").strip()
    if test_channel_id:
        test_channel_info(test_channel_id)
    else:
        print("No channel ID provided")
