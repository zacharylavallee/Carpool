#!/usr/bin/env python3
"""
Test Slack API Permissions
Diagnose exactly what's failing in the Slack API calls
"""

import os
from dotenv import load_dotenv
from slack_bolt import App

# Load environment variables
load_dotenv()

def test_slack_api():
    """Test Slack API calls to diagnose the permission issue"""
    print("🔍 Testing Slack API permissions...")
    print("=" * 60)
    
    # Initialize the app
    app = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
    )
    
    # Test channel ID from your debug output
    test_channel_id = "C097MRL9RU4"  # testtrip channel
    
    print(f"📋 Testing with channel: {test_channel_id}")
    
    # Test 1: Basic auth test
    print("\n🔐 Test 1: Basic authentication...")
    try:
        auth_result = app.client.auth_test()
        print(f"   ✅ Auth successful!")
        print(f"   📱 Bot User ID: {auth_result.get('user_id')}")
        print(f"   🏢 Team: {auth_result.get('team')}")
        print(f"   👤 User: {auth_result.get('user')}")
    except Exception as e:
        print(f"   ❌ Auth failed: {e}")
        return
    
    # Test 2: Channel members
    print(f"\n👥 Test 2: Getting channel members for {test_channel_id}...")
    try:
        members_result = app.client.conversations_members(channel=test_channel_id)
        members = members_result.get("members", [])
        print(f"   ✅ Got {len(members)} members: {members}")
    except Exception as e:
        print(f"   ❌ Failed to get channel members: {e}")
        print(f"   🔍 Error type: {type(e).__name__}")
        print(f"   📝 Error details: {str(e)}")
        
        # Check for specific error types
        error_str = str(e).lower()
        if "missing_scope" in error_str:
            print("   💡 This is a scope/permission issue")
        elif "not_in_channel" in error_str:
            print("   💡 Bot is not in the channel")
        elif "channel_not_found" in error_str:
            print("   💡 Channel doesn't exist or bot can't see it")
        elif "invalid_auth" in error_str:
            print("   💡 Authentication token issue")
    
    # Test 3: Channel info
    print(f"\n📢 Test 3: Getting channel info for {test_channel_id}...")
    try:
        channel_result = app.client.conversations_info(channel=test_channel_id)
        channel_info = channel_result.get("channel", {})
        print(f"   ✅ Channel name: {channel_info.get('name')}")
        print(f"   📊 Channel type: {channel_info.get('is_private', 'unknown')}")
        print(f"   👥 Member count: {channel_info.get('num_members', 'unknown')}")
    except Exception as e:
        print(f"   ❌ Failed to get channel info: {e}")
    
    # Test 4: User info for bot itself
    print(f"\n🤖 Test 4: Getting bot's own user info...")
    try:
        bot_user_id = auth_result.get('user_id')
        if bot_user_id:
            user_result = app.client.users_info(user=bot_user_id)
            user_info = user_result.get("user", {})
            print(f"   ✅ Bot name: {user_info.get('name')}")
            print(f"   🤖 Is bot: {user_info.get('is_bot')}")
        else:
            print("   ❌ No bot user ID available")
    except Exception as e:
        print(f"   ❌ Failed to get bot user info: {e}")
    
    # Test 5: Test with a different channel (if available)
    other_channels = ["C09870D81DE", "C097JTR2HTP"]  # lolol and devoted25 channels
    for channel_id in other_channels:
        print(f"\n🔄 Test 5: Testing alternate channel {channel_id}...")
        try:
            members_result = app.client.conversations_members(channel=channel_id)
            members = members_result.get("members", [])
            print(f"   ✅ Channel {channel_id}: {len(members)} members")
            break  # If one works, we know the API is working
        except Exception as e:
            print(f"   ❌ Channel {channel_id} failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Diagnosis complete!")
    print("\n💡 Common solutions:")
    print("   1. Make sure bot is added to the channel (/invite @Carpool)")
    print("   2. Try in a public channel first")
    print("   3. Check if workspace admin approval is needed")
    print("   4. Verify bot token hasn't expired")

if __name__ == "__main__":
    try:
        test_slack_api()
    except Exception as e:
        print(f"❌ Test script failed: {e}")
        print("💡 Check your .env file has SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET")
