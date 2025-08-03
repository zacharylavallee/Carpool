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
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "No active trips found. Use `/trip TripName` in a channel to create one!"
                }
            })
        else:
            for trip in trips:
                trip_name, channel_id, trip_creator = trip
                
                # Add trip header
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🎯 {trip_name}*"
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
                            "text": "   _No cars created yet_"
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
                        member_list = []
                        
                        for member in members:
                            username = get_username(member['user_id'])
                            if member['user_id'] == car_owner:
                                member_list.append(f"👤 {username} (Owner)")
                            else:
                                member_list.append(f"👤 {username}")
                        
                        # Add empty seat indicators
                        empty_seats = total_seats - filled_seats
                        for _ in range(empty_seats):
                            member_list.append("[ Empty ]")
                        
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"   🚗 *Car {car_id}: {car_name}* ({filled_seats}/{total_seats} seats)\n   {' | '.join(member_list)}"
                            }
                        })
                
                # Get users who need rides (not in any car for this trip)
                cur.execute("""
                    SELECT DISTINCT u.user_id
                    FROM (
                        -- This would ideally get channel members, but for now we'll skip
                        -- the "need rides" section until we can properly get channel membership
                        SELECT NULL as user_id WHERE FALSE
                    ) u
                """)
                
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"🔄 _Last updated: just now_"
                        }
                    ]
                })
                
                blocks.append({"type": "divider"})
        
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
