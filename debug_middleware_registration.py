#!/usr/bin/env python3
"""
Debug script to check if middleware is properly registered
"""

from app import bolt_app

def check_middleware_registration():
    """Check if our middleware is registered with the bolt app"""
    
    print("🔍 Checking middleware registration...")
    
    # Check if the bolt app has middleware
    if hasattr(bolt_app, '_middleware_list'):
        middleware_list = bolt_app._middleware_list
        print(f"📊 Found {len(middleware_list)} middleware functions:")
        
        for i, middleware in enumerate(middleware_list):
            print(f"   {i+1}. {middleware.__name__ if hasattr(middleware, '__name__') else str(middleware)}")
            
            # Check if it's our channel restriction middleware
            if hasattr(middleware, '__name__') and 'restrict_to_private_channels' in middleware.__name__:
                print("   ✅ Found our channel restriction middleware!")
            elif 'channel' in str(middleware).lower():
                print("   🔍 Found channel-related middleware")
    else:
        print("❌ No middleware list found on bolt_app")
    
    # Check if the app has any listeners
    if hasattr(bolt_app, '_listeners'):
        listeners = bolt_app._listeners
        print(f"\n📊 Found {len(listeners)} listeners registered")
        
        # Check for command listeners
        command_listeners = [l for l in listeners if hasattr(l, 'matchers') and any('command' in str(m) for m in l.matchers)]
        print(f"📊 Found {len(command_listeners)} command listeners")
        
        for listener in command_listeners[:5]:  # Show first 5
            if hasattr(listener, 'matchers'):
                for matcher in listener.matchers:
                    if hasattr(matcher, 'command') and matcher.command:
                        print(f"   - Command: /{matcher.command}")
    
    print("\n🎯 Testing middleware function directly...")
    
    # Test the middleware function directly
    try:
        from middleware.channel_restrictions import register_channel_restrictions
        print("✅ Successfully imported middleware registration function")
        
        # Check if we can access the middleware function
        import middleware.channel_restrictions as mcr
        if hasattr(mcr, 'restrict_to_private_channels'):
            print("✅ Found restrict_to_private_channels function in module")
        else:
            print("❌ restrict_to_private_channels function not found in module")
            
    except Exception as e:
        print(f"❌ Error importing middleware: {e}")

if __name__ == "__main__":
    check_middleware_registration()
