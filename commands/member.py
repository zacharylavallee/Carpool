"""
Member management commands for the carpool bot
"""
import psycopg2
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, post_announce, get_channel_members
from utils.channel_guard import check_bot_channel_access

def register_member_commands(bolt_app):
    """Register member management commands"""
    
    @bolt_app.command("/in")
    def cmd_in(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        car_id_str = (command.get("text") or "").strip()
        if not car_id_str:
            return eph(respond, "Usage: `/in CarID`")
        try:
            car_id = int(car_id_str)
        except ValueError:
            return eph(respond, ":x: CarID must be a number.")
        user = command["user_id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT created_by, name, trip FROM cars WHERE id=%s", (car_id,))
            row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Car `{car_id}` does not exist.")
        creator, car_name, trip = row
        if creator == user:
            return eph(respond, ":x: You can't request to join your own car.")
        
        with get_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO join_requests(car_id, user_id) VALUES(%s,%s)",
                    (car_id, user)
                )
                conn.commit()
            except psycopg2.errors.UniqueViolation:
                return eph(respond, f":x: You already requested to join car `{car_id}`.")
        
        # Send interactive message to car creator
        bolt_app.client.chat_postMessage(
            channel=creator,
            text=f":wave: <@{user}> wants to join your car `{car_id}` (*{car_name}*) on *{trip}*.",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":wave: *<@{user}> wants to join your car `{car_id}`*\n:car: Car: *{car_name}*\n:round_pushpin: Trip: *{trip}*"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "action_id": "approve_request",
                            "value": f"{car_id}:{user}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Deny"},
                            "style": "danger",
                            "action_id": "deny_request",
                            "value": f"{car_id}:{user}"
                        }
                    ]
                }
            ]
        )
        eph(respond, f":hourglass_flowing_sand: Join request sent for car `{car_id}`.")

    @bolt_app.action("approve_request")
    def act_approve(ack, body, client):
        ack()
        car_id, user_to_add = body["actions"][0]["value"].split(":")
        car_id = int(car_id)
        channel_id = body["channel"]["id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT trip FROM cars WHERE id=%s", (car_id,))
            trip = cur.fetchone()[0]
            cur.execute("DELETE FROM join_requests WHERE car_id=%s AND user_id=%s", (car_id, user_to_add))
            cur.execute("INSERT INTO car_members(car_id, user_id) VALUES(%s,%s)", (car_id, user_to_add))
            conn.commit()
        client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":white_check_mark: Approved <@{user_to_add}> for car `{car_id}`.", blocks=[])
        client.chat_postMessage(channel=user_to_add, text=f":white_check_mark: You were approved for car `{car_id}`.")
        post_announce(trip, channel_id, f":seat: <@{user_to_add}> joined car `{car_id}` on *{trip}*.")

    @bolt_app.action("deny_request")
    def act_deny(ack, body, client):
        ack()
        car_id, user_to_deny = body["actions"][0]["value"].split(":")
        car_id = int(car_id)
        
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM join_requests WHERE car_id=%s AND user_id=%s", (car_id, user_to_deny))
            conn.commit()
        client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":x: Denied <@{user_to_deny}> for car `{car_id}`.", blocks=[])
        client.chat_postMessage(channel=user_to_deny, text=f":x: Your request for car `{car_id}` was denied.")

    @bolt_app.command("/out")
    def cmd_out(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        user = command["user_id"]
        
        # Get the active trip for this channel
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM trips WHERE channel_id=%s AND active=TRUE", (channel_id,))
            trip_row = cur.fetchone()
            
            if not trip_row:
                return eph(respond, ":x: No active trip in this channel. Create one with `/trip TripName` first.")
            
            trip = trip_row[0]
            
            # Find which car the user is in for this trip
            cur.execute(
                """
                SELECT c.id, c.name, c.created_by 
                FROM cars c
                JOIN car_members cm ON c.id = cm.car_id
                WHERE c.channel_id=%s AND c.trip=%s AND cm.user_id=%s
                """,
                (channel_id, trip, user)
            )
            car_row = cur.fetchone()
            
            if not car_row:
                return eph(respond, f":x: You are not in any car on *{trip}*.")
            
            car_id, car_name, car_creator = car_row
            
            # Check if the user leaving is the car owner
            if user == car_creator:
                # Owner is leaving - delete the entire car and all its members
                cur.execute("DELETE FROM car_members WHERE car_id=%s", (car_id,))
                cur.execute("DELETE FROM cars WHERE id=%s", (car_id,))
                conn.commit()
                
                eph(respond, f":white_check_mark: You left and deleted your car *{car_name}* (car `{car_id}`).")  
                post_announce(trip, channel_id, f":boom: <@{user}> left and deleted car `{car_id}` (*{car_name}*) on *{trip}*.");
            else:
                # Regular member leaving - just remove them from the car
                cur.execute("DELETE FROM car_members WHERE car_id=%s AND user_id=%s", (car_id, user))
                conn.commit()
                
                eph(respond, f":white_check_mark: You left *{car_name}* (car `{car_id}`).")  
                post_announce(trip, channel_id, f":dash: <@{user}> left car `{car_id}` on *{trip}*.");

    @bolt_app.command("/boot")
    def cmd_boot(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        user_mention = (command.get("text") or "").strip()
        
        # Debug: Log what we received
        print(f"🔍 /boot command received text: '{user_mention}'")
        print(f"🔍 /boot command text length: {len(user_mention)}")
        print(f"🔍 /boot command text repr: {repr(user_mention)}")
        
        if not user_mention:
            return eph(respond, "Usage: `/boot @user`")
        
        # Extract user ID from mention - handle multiple formats
        target_user = None
        
        # Format 1: Proper Slack mention <@U123456789> or <@U123456789|username>
        if user_mention.startswith("<@") and user_mention.endswith(">"):
            mention_content = user_mention[2:-1]
            if "|" in mention_content:
                target_user = mention_content.split("|")[0]  # Take only the user ID part
            else:
                target_user = mention_content
            print(f"✅ /boot parsed Slack mention format: target_user='{target_user}'")
        
        # Format 2: Display name format - try to find user by display name or real name
        else:
            # Remove @ if present at the start
            search_name = user_mention.lstrip('@')
            print(f"🔍 /boot trying to find user by name: '{search_name}'")
            
            try:
                from app import bolt_app
                # Get channel members to search through
                channel_members = get_channel_members(channel_id)
                print(f"🔍 /boot found {len(channel_members)} channel members: {channel_members[:5]}...")  # Show first 5 for debugging
                
                if not channel_members:
                    print(f"❌ /boot no channel members found - this might be a permissions issue")
                    return eph(respond, f":x: Could not retrieve channel members. Make sure the bot has proper permissions and is added to this channel.")
                
                found_users = []  # Track all users we check for better debugging
                
                for member_id in channel_members:
                    try:
                        user_info = bolt_app.client.users_info(user=member_id)
                        user_data = user_info["user"]
                        
                        # Skip bots
                        if user_data.get("is_bot", False):
                            continue
                            
                        # Check various name fields
                        display_name = user_data.get("display_name", "")
                        real_name = user_data.get("real_name", "")
                        name = user_data.get("name", "")
                        
                        found_users.append(f"{name}({real_name})")
                        
                        # More flexible matching - try multiple approaches
                        search_lower = search_name.lower()
                        
                        # Exact username match
                        if search_lower == name.lower():
                            target_user = member_id
                            print(f"✅ /boot found exact username match: '{search_name}' -> {member_id} (@{name})")
                            break
                            
                        # Contains match in real name or display name
                        if (search_lower in real_name.lower() or 
                            search_lower in display_name.lower()):
                            target_user = member_id
                            print(f"✅ /boot found name match: '{search_name}' -> {member_id} ({real_name})")
                            break
                            
                        # Try matching parts of the name (e.g., "rohrbaugh.joshua" matches "rohrbaugh")
                        name_parts = search_lower.replace('.', ' ').split()
                        for part in name_parts:
                            if (part in real_name.lower() or 
                                part in display_name.lower() or 
                                part in name.lower()):
                                target_user = member_id
                                print(f"✅ /boot found partial match: '{part}' in user {member_id} ({real_name})")
                                break
                        if target_user:
                            break
                            
                    except Exception as e:
                        print(f"❌ /boot error checking user {member_id}: {e}")
                        continue
                
                print(f"🔍 /boot checked users: {found_users[:10]}...")  # Show first 10 users we found
                        
            except Exception as e:
                print(f"❌ /boot error searching for user by name: {e}")
        
        if not target_user:
            return eph(respond, f":x: Could not find user '{user_mention}'. Please use @mention to select the user from the dropdown, or make sure they're in this channel.")
        
        user = command["user_id"]
        
        # Get the active trip for this channel
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM trips WHERE channel_id=%s AND active=TRUE", (channel_id,))
            trip_row = cur.fetchone()
            
            if not trip_row:
                return eph(respond, ":x: No active trip in this channel. Create one with `/trip TripName` first.")
            
            trip = trip_row[0]
            
            # Find the user's car in this trip
            cur.execute(
                "SELECT id, name FROM cars WHERE channel_id=%s AND trip=%s AND created_by=%s",
                (channel_id, trip, user)
            )
            car_row = cur.fetchone()
            
            if not car_row:
                return eph(respond, f":x: You don't have a car on *{trip}* to remove members from.")
            
            car_id, car_name = car_row
            
            # Check if target user is actually in the car
            cur.execute(
                "SELECT 1 FROM car_members WHERE car_id=%s AND user_id=%s",
                (car_id, target_user)
            )
            if not cur.fetchone():
                return eph(respond, f":x: <@{target_user}> is not in your car.")
            
            # Remove the user from the car
            cur.execute("DELETE FROM car_members WHERE car_id=%s AND user_id=%s", (car_id, target_user))
            conn.commit()
        
        eph(respond, f":white_check_mark: You removed <@{target_user}> from your car (*{car_name}*).")
        bolt_app.client.chat_postMessage(
            channel=target_user, 
            text=f":boot: You were removed from *{car_name}* on *{trip}*."
        )
        post_announce(
            trip, channel_id, 
            f":boot: <@{user}> removed <@{target_user}> from *{car_name}* on *{trip}*."
        )
    
    @bolt_app.command("/add")
    def cmd_add(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        user_mention = (command.get("text") or "").strip()
        
        # Debug: Log what we received
        print(f"🔍 /add command received text: '{user_mention}'")
        print(f"🔍 /add command text length: {len(user_mention)}")
        print(f"🔍 /add command text repr: {repr(user_mention)}")
        
        if not user_mention:
            return eph(respond, "Usage: `/add @user`")
        
        # Extract user ID from mention - handle multiple formats (same logic as /boot)
        target_user = None
        
        # Format 1: Proper Slack mention <@U123456789> or <@U123456789|username>
        if user_mention.startswith("<@") and user_mention.endswith(">"):
            mention_content = user_mention[2:-1]
            if "|" in mention_content:
                target_user = mention_content.split("|")[0]  # Take only the user ID part
            else:
                target_user = mention_content
            print(f"✅ /add parsed Slack mention format: target_user='{target_user}'")
        
        # Format 2: Display name format - try to find user by display name or real name
        else:
            # Remove @ if present at the start
            search_name = user_mention.lstrip('@')
            print(f"🔍 /add trying to find user by name: '{search_name}'")
            
            try:
                from app import bolt_app
                # Get channel members to search through
                channel_members = get_channel_members(channel_id)
                print(f"🔍 /add found {len(channel_members)} channel members: {channel_members[:5]}...")  # Show first 5 for debugging
                
                if not channel_members:
                    print(f"❌ /add no channel members found - this might be a permissions issue")
                    return eph(respond, f":x: Could not retrieve channel members. Make sure the bot has proper permissions and is added to this channel.")
                
                found_users = []  # Track all users we check for better debugging
                
                for member_id in channel_members:
                    try:
                        user_info = bolt_app.client.users_info(user=member_id)
                        user_data = user_info["user"]
                        
                        # Skip bots
                        if user_data.get("is_bot", False):
                            continue
                            
                        # Check various name fields
                        display_name = user_data.get("display_name", "")
                        real_name = user_data.get("real_name", "")
                        name = user_data.get("name", "")
                        
                        found_users.append(f"{name}({real_name})")
                        
                        # More flexible matching - try multiple approaches
                        search_lower = search_name.lower()
                        
                        # Exact username match
                        if search_lower == name.lower():
                            target_user = member_id
                            print(f"✅ /add found exact username match: '{search_name}' -> {member_id} (@{name})")
                            break
                            
                        # Contains match in real name or display name
                        if (search_lower in real_name.lower() or 
                            search_lower in display_name.lower()):
                            target_user = member_id
                            print(f"✅ /add found name match: '{search_name}' -> {member_id} ({real_name})")
                            break
                            
                        # Try matching parts of the name (e.g., "rohrbaugh.joshua" matches "rohrbaugh")
                        name_parts = search_lower.replace('.', ' ').split()
                        for part in name_parts:
                            if (part in real_name.lower() or 
                                part in display_name.lower() or 
                                part in name.lower()):
                                target_user = member_id
                                print(f"✅ /add found partial match: '{part}' in user {member_id} ({real_name})")
                                break
                        if target_user:
                            break
                            
                    except Exception as e:
                        print(f"❌ /add error checking user {member_id}: {e}")
                        continue
                
                print(f"🔍 /add checked users: {found_users[:10]}...")  # Show first 10 users we found
                        
            except Exception as e:
                print(f"❌ /add error searching for user by name: {e}")
        
        if not target_user:
            return eph(respond, f":x: Could not find user '{user_mention}'. Please use @mention to select the user from the dropdown, or make sure they're in this channel.")
        
        user = command["user_id"]
        
        # Don't allow adding yourself
        if target_user == user:
            return eph(respond, ":x: You can't add yourself to your own car.")
        
        # Get the active trip for this channel
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM trips WHERE channel_id=%s AND active=TRUE", (channel_id,))
            trip_row = cur.fetchone()
            
            if not trip_row:
                return eph(respond, ":x: No active trip in this channel. Create one with `/trip TripName` first.")
            
            trip = trip_row[0]
            
            # Find the user's car in this trip
            cur.execute(
                "SELECT id, name, seats FROM cars WHERE channel_id=%s AND trip=%s AND created_by=%s",
                (channel_id, trip, user)
            )
            car_row = cur.fetchone()
            
            if not car_row:
                return eph(respond, f":x: You don't have a car on *{trip}* to add members to.")
            
            car_id, car_name, total_seats = car_row
            
            # Check if target user is already in ANY car for this trip
            cur.execute(
                "SELECT c.name, c.created_by FROM car_members cm JOIN cars c ON cm.car_id = c.id WHERE cm.user_id=%s AND c.trip=%s AND c.channel_id=%s",
                (target_user, trip, channel_id)
            )
            existing_car = cur.fetchone()
            
            if existing_car:
                existing_car_name, existing_car_owner = existing_car
                return eph(respond, f":x: <@{target_user}> is already in *{existing_car_name}* (owned by <@{existing_car_owner}>) on *{trip}*.")
            
            # Check if car has space
            cur.execute("SELECT COUNT(*) FROM car_members WHERE car_id=%s", (car_id,))
            current_members = cur.fetchone()[0]
            
            if current_members >= total_seats:
                return eph(respond, f":x: Your car (*{car_name}*) is full ({current_members}/{total_seats} seats). Use `/update` to increase seats or `/boot` to remove someone first.")
            
            # Add the user to the car
            try:
                cur.execute(
                    "INSERT INTO car_members(car_id, user_id) VALUES(%s, %s)",
                    (car_id, target_user)
                )
                conn.commit()
            except psycopg2.errors.UniqueViolation:
                return eph(respond, f":x: <@{target_user}> is already in your car.")
        
        eph(respond, f":white_check_mark: You added <@{target_user}> to your car (*{car_name}*).")
        bolt_app.client.chat_postMessage(
            channel=target_user, 
            text=f":car: You were added to *{car_name}* on *{trip}* by <@{user}>."
        )
        post_announce(
            trip, channel_id, 
            f":seat: <@{user}> added <@{target_user}> to *{car_name}* on *{trip}*."
        )
