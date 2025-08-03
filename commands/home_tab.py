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
    
    @bolt_app.action("car_actions_*")
    def handle_car_actions(ack, body, client):
        """Handle car action dropdown selections"""
        ack()
        
        # Extract action details
        selected_option = body["actions"][0]["selected_option"]
        action_value = selected_option["value"]
        user_id = body["user"]["id"]
        
        # Parse action type and car ID
        if "_car_" in action_value:
            action_type = action_value.split("_car_")[0]
            car_id = action_value.split("_car_")[1]
        else:
            print(f"Invalid action value: {action_value}")
            return
        
        try:
            if action_type == "join":
                # Show join confirmation modal
                client.views_open(
                    trigger_id=body["trigger_id"],
                    view={
                        "type": "modal",
                        "title": {
                            "type": "plain_text",
                            "text": f"Join Car #{car_id}"
                        },
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"🚗 *Join Car #{car_id}*\n\n_Interactive join functionality coming soon!_\n\nFor now, go to the channel and use `/in {car_id}` to join this car."
                                }
                            }
                        ],
                        "close": {
                            "type": "plain_text",
                            "text": "Close"
                        }
                    }
                )
            
            elif action_type == "leave":
                # Show leave confirmation modal
                client.views_open(
                    trigger_id=body["trigger_id"],
                    view={
                        "type": "modal",
                        "title": {
                            "type": "plain_text",
                            "text": "Leave Car"
                        },
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"💪 *Leave Car #{car_id}*\n\n_Interactive leave functionality coming soon!_\n\nFor now, go to the channel and use `/out` to leave this car."
                                }
                            }
                        ],
                        "close": {
                            "type": "plain_text",
                            "text": "Close"
                        }
                    }
                )
            
            elif action_type == "add":
                # Show add person modal
                client.views_open(
                    trigger_id=body["trigger_id"],
                    view={
                        "type": "modal",
                        "title": {
                            "type": "plain_text",
                            "text": "Add Someone"
                        },
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"👥 *Add Someone to Car #{car_id}*\n\n_Interactive add functionality coming soon!_\n\nFor now, ask them to go to the channel and use `/in {car_id}` to join."
                                }
                            }
                        ],
                        "close": {
                            "type": "plain_text",
                            "text": "Close"
                        }
                    }
                )
            
            elif action_type == "boot":
                # Show boot person modal
                client.views_open(
                    trigger_id=body["trigger_id"],
                    view={
                        "type": "modal",
                        "title": {
                            "type": "plain_text",
                            "text": "Boot Someone"
                        },
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"👎 *Boot Someone from Car #{car_id}*\n\n_Interactive boot functionality coming soon!_\n\nFor now, go to the channel and use `/boot @username` to remove someone."
                                }
                            }
                        ],
                        "close": {
                            "type": "plain_text",
                            "text": "Close"
                        }
                    }
                )
            
            elif action_type == "delete":
                # Show delete car confirmation modal
                client.views_open(
                    trigger_id=body["trigger_id"],
                    view={
                        "type": "modal",
                        "title": {
                            "type": "plain_text",
                            "text": "Delete Car"
                        },
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"🗑️ *Delete Car #{car_id}*\n\n⚠️ This will remove the car and all its passengers.\n\n_Interactive delete functionality coming soon!_\n\nFor now, go to the channel and use `/cancel {car_id}` to delete this car."
                                }
                            }
                        ],
                        "close": {
                            "type": "plain_text",
                            "text": "Close"
                        }
                    }
                )
            
            elif action_type == "view":
                # Show car details modal
                client.views_open(
                    trigger_id=body["trigger_id"],
                    view={
                        "type": "modal",
                        "title": {
                            "type": "plain_text",
                            "text": f"Car #{car_id} Details"
                        },
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"📝 *Car #{car_id} Details*\n\n_Detailed car information coming soon!_\n\nThis will show car details, passenger list, and trip information."
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
            print(f"Error handling car action {action_type}: {e}")

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
                
                # Trip header section (no channel button)
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🎯 *{trip_name.upper()}* • #{channel_name}"
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
                        
                        # Determine user's relationship to this car
                        user_in_car = any(member['user_id'] == user_id for member in members)
                        is_car_owner = car_owner == user_id
                        car_is_full = filled_seats >= total_seats
                        
                        # Build user-specific dropdown options
                        dropdown_options = []
                        
                        if is_car_owner:
                            # Car owner options
                            dropdown_options.extend([
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "👥 Add Someone"
                                    },
                                    "value": f"add_to_car_{car_id}"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "👎 Boot Someone"
                                    },
                                    "value": f"boot_from_car_{car_id}"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "🗑️ Delete Car"
                                    },
                                    "value": f"delete_car_{car_id}"
                                }
                            ])
                            if user_in_car:
                                dropdown_options.append({
                                    "text": {
                                        "type": "plain_text",
                                        "text": "💪 Leave Car"
                                    },
                                    "value": f"leave_car_{car_id}"
                                })
                        elif user_in_car:
                            # User is in car but not owner
                            dropdown_options.append({
                                "text": {
                                    "type": "plain_text",
                                    "text": "💪 Leave Car"
                                },
                                "value": f"leave_car_{car_id}"
                            })
                        elif not car_is_full:
                            # User not in car and car has space
                            dropdown_options.append({
                                "text": {
                                    "type": "plain_text",
                                    "text": "🚗 Join Car"
                                },
                                "value": f"join_car_{car_id}"
                            })
                        
                        # Add view info option for everyone
                        dropdown_options.append({
                            "text": {
                                "type": "plain_text",
                                "text": "📝 View Details"
                            },
                            "value": f"view_car_{car_id}"
                        })
                        
                        # Car card layout with user-specific dropdown
                        accessory = None
                        if dropdown_options:
                            accessory = {
                                "type": "overflow",
                                "options": dropdown_options,
                                "action_id": f"car_actions_{car_id}"
                            }
                        
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"🚗 *{car_name}* (Car #{car_id})\n{status} `{filled_seats}/{total_seats} seats`\n\n```\n{car_visual}\n```"
                            },
                            "accessory": accessory
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
