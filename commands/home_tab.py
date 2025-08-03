"""
App Home Tab Dashboard for the carpool bot
Provides a private, real-time view of carpool status without channel noise
"""
import psycopg2.extras
from config.database import get_conn
from utils.helpers import get_username

def build_car_visualization(driver_name, passengers, total_seats):
    """Build a top-down car visualization with seats arranged in standard layout"""
    
    # Create seat array: [driver, front_passenger, back_left, back_right, back_left2, back_right2, ...]
    seats = []
    
    # Add driver (always front-left)
    if driver_name:
        seats.append(f"[{driver_name[:8]}]")
    else:
        seats.append("[ - ]")
    
    # Add passengers to remaining seats
    passenger_index = 0
    for seat_num in range(1, total_seats):
        if passenger_index < len(passengers):
            passenger_name = passengers[passenger_index][:8]  # Limit to 8 chars
            seats.append(f"[{passenger_name}]")
            passenger_index += 1
        else:
            seats.append("[ - ]")
    
    # Arrange seats in car layout (2 seats per row)
    car_rows = []
    for i in range(0, len(seats), 2):
        if i + 1 < len(seats):
            # Two seats in this row
            car_rows.append(f"{seats[i]} {seats[i+1]}")
        else:
            # Single seat in this row (odd number of seats)
            car_rows.append(f"{seats[i]}")
    
    return "\n".join(car_rows)

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
    
    @bolt_app.action("manage_car_*")
    def handle_manage_car(ack, body, client):
        """Handle car management button clicks"""
        ack()
        
        # Extract car ID from action_id
        action_id = body["actions"][0]["action_id"]
        car_id = action_id.replace("manage_car_", "")
        user_id = body["user"]["id"]
        
        # For now, show a simple modal with car management options
        try:
            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "title": {
                        "type": "plain_text",
                        "text": f"Manage Car #{car_id}"
                    },
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"🚗 *Car Management*\n\nCar ID: #{car_id}\n\n_Interactive car management features coming soon!_\n\nFor now, use slash commands in the channel:"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "• `/in` - Join this car\n• `/out` - Leave this car\n• `/car [name]` - Create a new car"
                            }
                        }
                    ],
                    "close": {
                        "type": "plain_text",
                        "text": "Close"
                    }
                }
            )
        except Exception as e:
            print(f"Error opening car management modal: {e}")
    
    @bolt_app.action("view_channel_*")
    def handle_view_channel(ack, body, client):
        """Handle channel button clicks"""
        ack()
        
        # Extract channel ID from action_id
        action_id = body["actions"][0]["action_id"]
        channel_id = action_id.replace("view_channel_", "")
        user_id = body["user"]["id"]
        
        # Send a message to guide user to the channel
        try:
            client.chat_postEphemeral(
                channel=user_id,  # Send as DM
                user=user_id,
                text=f"🎯 To manage this trip, go to <#{channel_id}> and use slash commands like `/car`, `/in`, `/out`, etc."
            )
        except Exception as e:
            print(f"Error sending channel guidance message: {e}")

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
                        "text": "📭 *No Active Trips*\n\nGet started by creating a trip in any channel!"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "💡 Use `/trip [name]` in a channel to create your first carpool"
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
                
                # Get channel name for display
                try:
                    from app import bolt_app
                    channel_info = bolt_app.client.conversations_info(channel=channel_id)
                    channel_name = channel_info['channel']['name']
                except:
                    channel_name = channel_id[-8:]  # Fallback to ID suffix
                
                # Trip header section with channel info
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🎯 *{trip_name.upper()}*"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": f"#{channel_name}"
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
                            "text": "⚠️ *No cars created*\nUse `/car [name]` to add the first car"
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
                        
                        # Build passenger list with first names only
                        passengers = []
                        owner_first_name = ""
                        
                        for member in members:
                            username = get_username(member['user_id'])
                            first_name = username.split()[0] if username else "Unknown"
                            
                            if member['user_id'] == car_owner:
                                owner_first_name = first_name
                            else:
                                passengers.append(first_name)
                        
                        # Create virtual car visualization (top-down view)
                        car_visual = build_car_visualization(owner_first_name, passengers, total_seats)
                        
                        # Determine status and color
                        if filled_seats == total_seats:
                            status = "🔴 *FULL*"
                            style = "danger"
                        elif filled_seats == 0:
                            status = "⚪ *EMPTY*"
                            style = "primary"
                        else:
                            status = "🟡 *AVAILABLE*"
                            style = "primary"
                        
                        # Car card layout with virtual car visualization
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"🚗 *{car_name}* (Car #{car_id})\n{status} `{filled_seats}/{total_seats} seats`\n\n```\n{car_visual}\n```"
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
                            "text": f"🔄 _Last updated: just now_ • 📍 <#{channel_id}>"
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
