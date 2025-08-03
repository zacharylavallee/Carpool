"""
App Home Tab Dashboard for the carpool bot
Provides a private, real-time view of carpool status without channel noise
"""
import psycopg2.extras
from config.database import get_conn
from utils.helpers import get_username

def register_home_tab_handlers(bolt_app):
    """Register App Home Tab event handlers"""
    
    @bolt_app.event("app_home_opened")
    def handle_app_home_opened(event, client):
        """Handle when user opens the App Home tab"""
        user_id = event["user"]
        
        # Build and publish the home tab view
        home_view = build_home_tab_view(user_id)
        
        try:
            client.views_publish(
                user_id=user_id,
                view=home_view
            )
        except Exception as e:
            print(f"Error publishing home tab view: {e}")

def build_home_tab_view(user_id):
    """Build the home tab dashboard view for a specific user"""
    
    # Get all active trips across channels the user is in
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get active trips (simplified - we'll enhance this to filter by user's channels)
        cur.execute("SELECT name, channel_id, created_by FROM trips WHERE active=TRUE ORDER BY name")
        trips = cur.fetchall()
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚗 Carpool Dashboard"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        if not trips:
            blocks.extend([
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📭 *No active trips found*\n\nUse `/trip TripName` in a channel to create one!"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "💡 Tip: Create trips in specific channels to organize carpools by destination or event"
                        }
                    ]
                }
            ])
        else:
            for i, trip in enumerate(trips):
                trip_name, channel_id, trip_creator = trip
                
                # Add spacing between trips (except for first trip)
                if i > 0:
                    blocks.append({"type": "divider"})
                
                # Trip header with better formatting
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🎯 *{trip_name.upper()}*"
                    }
                })
                
                # Get cars for this trip
                cur.execute("""
                    SELECT c.id, c.name, c.seats, c.created_by,
                           COUNT(cm.user_id) as filled_seats
                    FROM cars c
                    LEFT JOIN car_members cm ON c.id = cm.car_id
                    WHERE c.trip = %s AND c.channel_id = %s
                    GROUP BY c.id, c.name, c.seats, c.created_by
                    ORDER BY c.id
                """, (trip_name, channel_id))
                
                cars = cur.fetchall()
                
                if not cars:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "🚫 _No cars available yet_\n\nUse `/car CarName` in the channel to create one!"
                        }
                    })
                else:
                    for car in cars:
                        car_id, car_name, total_seats, car_owner, filled_seats = car
                        
                        # Get car members
                        cur.execute("""
                            SELECT cm.user_id
                            FROM car_members cm
                            WHERE cm.car_id = %s
                            ORDER BY cm.user_id
                        """, (car_id,))
                        
                        members = cur.fetchall()
                        
                        # Build member display with better formatting
                        member_display = []
                        for member in members:
                            username = get_username(member['user_id'])
                            if member['user_id'] == car_owner:
                                member_display.append(f"👨‍✈️ *{username}*")
                            else:
                                member_display.append(f"👤 {username}")
                        
                        # Add empty seat indicators with better styling
                        empty_seats = total_seats - filled_seats
                        for i in range(empty_seats):
                            member_display.append("💺 _Available_")
                        
                        # Determine car status emoji
                        if filled_seats == total_seats:
                            status_emoji = "🔴"  # Full
                        elif filled_seats == 0:
                            status_emoji = "⚪"  # Empty
                        else:
                            status_emoji = "🟡"  # Partially filled
                        
                        # Car section with cleaner layout
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{status_emoji} *{car_name}* • Car #{car_id}\n📊 *{filled_seats}/{total_seats} seats filled*\n\n{' • '.join(member_display)}"
                            }
                        })
                
                # Add trip summary context
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"🔄 _Updated just now_ • 📍 <#{channel_id}>"
                        }
                    ]
                })
        
        # Add footer with helpful info
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "💡 *Tip:* This dashboard updates automatically when changes are made. Use slash commands in channels to manage carpools!"
            }
        })
    
    return {
        "type": "home",
        "blocks": blocks
    }

def update_home_tab_for_all_users():
    """Update home tab for all users (called when carpool data changes)"""
    # This is a simplified version - in production we'd want to be more selective
    # about which users to update based on which channels they're in
    pass

def update_home_tab_for_user(user_id):
    """Update home tab for a specific user"""
    from app import bolt_app
    
    try:
        home_view = build_home_tab_view(user_id)
        bolt_app.client.views_publish(
            user_id=user_id,
            view=home_view
        )
    except Exception as e:
        print(f"Error updating home tab for user {user_id}: {e}")
