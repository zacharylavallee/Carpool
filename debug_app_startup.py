#!/usr/bin/env python3
"""
Debug script to check app startup and command registration
"""

import sys
import traceback

def debug_app_startup():
    """Debug the app startup process step by step"""
    
    print("🔍 Debugging app startup process...")
    
    try:
        print("\n1️⃣ Testing basic imports...")
        import os
        from flask import Flask, request, jsonify
        from slack_bolt import App
        from slack_bolt.adapter.flask import SlackRequestHandler
        print("✅ Basic imports successful")
        
        print("\n2️⃣ Testing database import...")
        from config.database import init_db
        print("✅ Database import successful")
        
        print("\n3️⃣ Testing utility imports...")
        from utils.helpers import eph
        print("✅ Utility imports successful")
        
        print("\n4️⃣ Testing command module imports...")
        try:
            from commands.help import register_help_commands
            print("✅ Help commands import successful")
        except Exception as e:
            print(f"❌ Help commands import failed: {e}")
            
        try:
            from commands.trip import register_trip_commands
            print("✅ Trip commands import successful")
        except Exception as e:
            print(f"❌ Trip commands import failed: {e}")
            
        try:
            from commands.car import register_car_commands
            print("✅ Car commands import successful")
        except Exception as e:
            print(f"❌ Car commands import failed: {e}")
            
        try:
            from commands.member import register_member_commands
            print("✅ Member commands import successful")
        except Exception as e:
            print(f"❌ Member commands import failed: {e}")
            
        try:
            from commands.manage import register_manage_commands
            print("✅ Manage commands import successful")
        except Exception as e:
            print(f"❌ Manage commands import failed: {e}")
            
        try:
            from commands.user import register_user_commands
            print("✅ User commands import successful")
        except Exception as e:
            print(f"❌ User commands import failed: {e}")
            
        print("\n5️⃣ Testing middleware import...")
        try:
            from middleware.channel_restrictions import register_channel_restrictions
            print("✅ Middleware import successful")
        except Exception as e:
            print(f"❌ Middleware import failed: {e}")
            
        print("\n6️⃣ Testing bolt app creation...")
        
        # Check environment variables
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        client_id = os.getenv("SLACK_CLIENT_ID")
        client_secret = os.getenv("SLACK_CLIENT_SECRET")
        
        print(f"   Bot token present: {'✅' if bot_token else '❌'}")
        print(f"   Signing secret present: {'✅' if signing_secret else '❌'}")
        print(f"   Client ID present: {'✅' if client_id else '❌'}")
        print(f"   Client secret present: {'✅' if client_secret else '❌'}")
        
        # Try to create bolt app like in app.py
        if client_id and client_secret:
            from slack_bolt.oauth import OAuthSettings
            oauth_settings = OAuthSettings(
                client_id=client_id,
                client_secret=client_secret,
                scopes=["commands", "chat:write", "groups:read", "im:write", "users:read"]
            )
            bolt_app = App(
                signing_secret=signing_secret,
                oauth_settings=oauth_settings
            )
            print("✅ OAuth bolt app created successfully")
        else:
            bolt_app = App(
                token=bot_token,
                signing_secret=signing_secret
            )
            print("✅ Token-based bolt app created successfully")
            
        print(f"   Bolt app type: {type(bolt_app)}")
        
        print("\n7️⃣ Testing command registration...")
        
        # Try registering commands one by one
        try:
            register_help_commands(bolt_app)
            print("✅ Help commands registered")
        except Exception as e:
            print(f"❌ Help commands registration failed: {e}")
            traceback.print_exc()
            
        # Check how many listeners we have now
        if hasattr(bolt_app, '_listeners'):
            print(f"   Listeners after help: {len(bolt_app._listeners)}")
            
        try:
            register_trip_commands(bolt_app)
            print("✅ Trip commands registered")
        except Exception as e:
            print(f"❌ Trip commands registration failed: {e}")
            traceback.print_exc()
            
        if hasattr(bolt_app, '_listeners'):
            print(f"   Listeners after trip: {len(bolt_app._listeners)}")
            
        print("\n8️⃣ Final listener count...")
        if hasattr(bolt_app, '_listeners'):
            listeners = bolt_app._listeners
            print(f"📊 Total listeners: {len(listeners)}")
            
            # Count command listeners
            command_count = 0
            for listener in listeners:
                if hasattr(listener, 'matchers'):
                    for matcher in listener.matchers:
                        if hasattr(matcher, 'command') and matcher.command:
                            command_count += 1
                            print(f"   - Command: /{matcher.command}")
                            
            print(f"📊 Total command listeners: {command_count}")
        
    except Exception as e:
        print(f"❌ Critical error during startup: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_app_startup()
