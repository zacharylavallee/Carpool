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
            # Empty state with clean design
            blocks.extend([
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":inbox_tray: *No Active Trips*\n\nGet started by creating a trip in any channel!"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": ":bulb: Use `/trip [name]` in a channel to create your first carpool"
                        }
                    ]
                }
            ])
        else:
            # Process each trip with structured layout
            for i, trip in enumerate(trips):
                trip_name, channel_id, trip_creator = trip
                
                # Add visual separation between trips
                if i > 0:
                    blocks.extend([
                        {"type": "divider"},
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": " "
                                }
                            ]
                        }
                    ])
                
                # Trip header section with channel info
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":dart: *{trip_name.upper()}*"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": f"#{channel_id[-8:]}"
                        },
                        "action_id": f"view_channel_{channel_id}",
                        "style": "primary"
                    }
                })
                
                # Get cars for this trip with member counts
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
                    # No cars state
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":warning: *No cars created*\nUse `/car [name]` to add the first car"
                        }
                    })
                else:
                    # Build cars grid-like layout
                    for car_idx, car in enumerate(cars):
                        car_id, car_name, total_seats, car_owner, filled_seats = car
                        
                        # Get car members for detailed display
                        cur.execute("""
                            SELECT cm.user_id
                            FROM car_members cm
                            WHERE cm.car_id = %s
                            ORDER BY cm.user_id
                        """, (car_id,))
                        
                        members = cur.fetchall()
                        
                        # Build passenger list
                        passengers = []
                        owner_name = ""
                        
                        for member in members:
                            username = get_username(member['user_id'])
                            if member['user_id'] == car_owner:
                                owner_name = username
                            else:
                                passengers.append(username)
                        
                        # Create visual seat representation
                        seat_display = []
                        if owner_name:
                            seat_display.append(f":bust_in_silhouette: *{owner_name}* (Driver)")
                        
                        for passenger in passengers:
                            seat_display.append(f":bust_in_silhouette: {passenger}")
                        
                        # Add empty seats
                        empty_seats = total_seats - filled_seats
                        for _ in range(empty_seats):
                            seat_display.append(":seat: _Open_")
                        
                        # Determine status and color
                        if filled_seats == total_seats:
                            status = ":red_circle: *FULL*"
                            style = "danger"
                        elif filled_seats == 0:
                            status = ":white_circle: *EMPTY*"
                            style = "primary"
                        else:
                            status = ":yellow_circle: *AVAILABLE*"
                            style = "primary"
                        
                        # Car card layout
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f":car: *{car_name}* (Car #{car_id})\n{status} `{filled_seats}/{total_seats} seats`\n\n{chr(10).join(seat_display)}"
                            },
                            "accessory": {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Manage"
                                },
                                "action_id": f"manage_car_{car_id}",
                                "style": style
                            }
                        })
                        
                        # Add subtle spacing between cars
                        if car_idx < len(cars) - 1:
                            blocks.append({
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "mrkdwn",
                                        "text": "\u00a0"
                                    }
                                ]
                            })
                
                # Trip summary footer
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f":arrows_counterclockwise: _Last updated: just now_ \u2022 :round_pushpin: <#{channel_id}>"
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
