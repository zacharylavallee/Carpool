"""
Channel event handlers for the carpool bot
Handles user join/leave events to maintain data consistency
"""
import psycopg2.extras
from config.database import get_conn
from utils.helpers import get_username, eph
# from commands.home_tab import update_home_tab_for_user  # DISABLED


def register_channel_event_handlers(bolt_app):
    """Register channel membership event handlers"""
    
    @bolt_app.event("member_left_channel")
    def handle_member_left_channel(event, client):
        """Handle when a user leaves a channel - remove them from any cars in that channel"""
        try:
            user_id = event["user"]
            channel_id = event["channel"]
            
            # Remove user from any cars in this channel's trip
            removed_cars = remove_user_from_channel_cars(user_id, channel_id)
            
            if removed_cars:
                # Home Tab update disabled
                # update_home_tab_for_user(user_id)
                
                # Log the automatic removal
                print(f"User {user_id} left channel {channel_id}, removed from {len(removed_cars)} car(s)")
                
                # Optionally notify other car members (via DM to avoid channel spam)
                for car_info in removed_cars:
                    car_name, trip_name = car_info
                    username = get_username(user_id)
                    
                    # Send DM to the user who was removed
                    try:
                        client.chat_postMessage(
                            channel=user_id,
                            text=f"🚗 You were automatically removed from **{car_name}** in trip **{trip_name}** because you left the channel."
                        )
                    except Exception as dm_error:
                        print(f"Could not send DM to {user_id}: {dm_error}")
                        
        except Exception as e:
            print(f"Error handling member_left_channel event: {e}")


def remove_user_from_channel_cars(user_id, channel_id):
    """
    Remove a user from all cars in the specified channel
    Returns list of (car_name, trip_name) tuples for cars they were removed from
    """
    removed_cars = []
    
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            # Find all cars the user is in for this channel
            cur.execute("""
                SELECT c.id, c.name, c.trip, c.created_by
                FROM cars c
                JOIN car_members cm ON c.id = cm.car_id
                WHERE cm.user_id = %s AND c.channel_id = %s
            """, (user_id, channel_id))
            
            user_cars = cur.fetchall()
            
            for car in user_cars:
                car_id, car_name, trip_name, car_owner = car
                
                if car_owner == user_id:
                    # User is the car owner - delete the entire car
                    cur.execute("DELETE FROM cars WHERE id = %s", (car_id,))
                    removed_cars.append((f"{car_name} (deleted - you were owner)", trip_name))
                    print(f"Deleted car {car_id} ({car_name}) - owner {user_id} left channel")
                else:
                    # User is just a member - remove them from the car
                    cur.execute("""
                        DELETE FROM car_members 
                        WHERE car_id = %s AND user_id = %s
                    """, (car_id, user_id))
                    removed_cars.append((car_name, trip_name))
                    print(f"Removed user {user_id} from car {car_id} ({car_name})")
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"Error removing user {user_id} from channel {channel_id} cars: {e}")
            raise
    
    return removed_cars
