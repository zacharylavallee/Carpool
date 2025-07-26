#!/usr/bin/env python3
"""
Debug script to test middleware channel detection
"""

def test_channel_detection():
    """Test channel ID detection logic"""
    
    test_channels = [
        ("C097MRL9RU4", "Public channel (should be blocked)"),
        ("G123456789", "Private group (should be allowed)"),
        ("D987654321", "Direct message (should be allowed)"),
        ("U123456789", "User ID in DM (should be allowed)"),
    ]
    
    print("🔍 Testing channel ID detection logic...")
    print("=" * 60)
    
    for channel_id, description in test_channels:
        if channel_id.startswith("C"):
            result = "❌ BLOCKED (Public channel)"
        elif channel_id.startswith("G"):
            result = "✅ ALLOWED (Private group)"
        elif channel_id.startswith("D"):
            result = "✅ ALLOWED (Direct message)"
        elif channel_id.startswith("U"):
            result = "✅ ALLOWED (User DM)"
        else:
            result = "❓ UNKNOWN"
        
        print(f"{channel_id}: {description} → {result}")
    
    print("\n" + "=" * 60)
    print("If you can create trips in public channels, the middleware")
    print("might not be working properly or the channel might not")
    print("be detected as public (starting with 'C').")

if __name__ == "__main__":
    test_channel_detection()
