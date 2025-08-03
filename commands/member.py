"""
Member management commands for the carpool bot
"""
import psycopg2
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, auto_dismiss_eph, auto_dismiss_eph_with_actions, get_channel_members, get_active_trip, post_announce, get_username
from utils.channel_guard import check_bot_channel_access

def add_users_to_car(car_id, channel_id, user_id, target_user_ids, client=None):
    """Standalone function to add users to a car. Returns (success, message, added_users)"""
    try:
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Get car and trip info
            cur.execute(
                "SELECT name, trip, created_by FROM cars WHERE id=%s AND channel_id=%s",
                (car_id, channel_id)
            )
            car_info = cur.fetchone()
            
            if not car_info:
                return False, "❌ Car not found.", []
            
            car_name, trip, car_owner = car_info
            
            # Check if user has permission to add to this car
            if user_id != car_owner:
                return False, "❌ Only the car owner can add people to their car.", []
            
            # Check conflicts and add users
            users_to_add = []
            already_in_car = []
            already_in_other_cars = []
            
            for target_user in target_user_ids:
                # Check if user is already in this car
                cur.execute(
                    "SELECT 1 FROM car_members WHERE car_id=%s AND user_id=%s",
                    (car_id, target_user)
                )
                if cur.fetchone():
                    already_in_car.append(target_user)
                    continue
                
                # Check if user is already in ANY other car for this trip
                cur.execute(
                    "SELECT c.name, c.created_by FROM car_members cm JOIN cars c ON cm.car_id = c.id WHERE cm.user_id=%s AND c.trip=%s AND c.channel_id=%s",
                    (target_user, trip, channel_id)
                )
                existing_car = cur.fetchone()
                
                if existing_car:
                    existing_car_name, existing_car_owner = existing_car
                    already_in_other_cars.append((target_user, existing_car_name, existing_car_owner))
                    continue
                
                users_to_add.append(target_user)
            
            # Build error messages for conflicts
            error_messages = []
            if already_in_car:
                mentions = [f"<@{uid}>" for uid in already_in_car]
                error_messages.append(f"Already in your car: {', '.join(mentions)}")
            
            if already_in_other_cars:
                conflicts = [f"<@{uid}> (in *{car_name}* by <@{owner}>)" for uid, car_name, owner in already_in_other_cars]
                error_messages.append(f"Already in other cars: {', '.join(conflicts)}")
            
            if not users_to_add:
                if error_messages:
                    return False, f"❌ No users added. {' | '.join(error_messages)}", []
                else:
                    return False, "❌ No valid users to add.", []
            
            # Add all valid users to the car
            added_users = []
            for target_user in users_to_add:
                try:
                    cur.execute(
                        "INSERT INTO car_members(car_id, user_id) VALUES(%s, %s)",
                        (car_id, target_user)
                    )
                    added_users.append(target_user)
                except Exception as e:
                    print(f"⚠️ add_users_to_car unexpected error for user {target_user}: {e}")
                    continue
            
            conn.commit()
            
            # Build success message
            if added_users:
                added_mentions = [f"<@{uid}>" for uid in added_users]
                success_msg = f"✅ You added {', '.join(added_mentions)} to your car (*{car_name}*)."
                
                if error_messages:
                    success_msg += f"\n\n⚠️ {' | '.join(error_messages)}"
                
                # Send DMs to added users if client is provided
                if client:
                    for target_user in added_users:
                        try:
                            client.chat_postMessage(
                                channel=target_user, 
                                text=f"🚗 You were added to *{car_name}* on *{trip}* by <@{user_id}>."
                            )
                        except Exception as e:
                            print(f"⚠️ add_users_to_car failed to send DM to {target_user}: {e}")
                
                # Post announcement
                if len(added_users) == 1:
                    announcement = f":seat: <@{user_id}> added <@{added_users[0]}> to *{car_name}* on *{trip}*."
                else:
                    announcement = f":seat: <@{user_id}> added {', '.join(added_mentions)} to *{car_name}* on *{trip}*."
                
                post_announce(trip, channel_id, announcement)
                
                return True, success_msg, added_users
            else:
                return False, "❌ No users were added.", []
                
    except Exception as e:
        print(f"Error in add_users_to_car: {e}")
        return False, f"❌ Error adding users: {str(e)}", []

def boot_users_from_car(car_id, channel_id, user_id, target_user_ids, client=None):
    """Standalone function to boot users from a car. Returns (success, message, booted_users)"""
    try:
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Get car and trip info
            cur.execute(
                "SELECT name, trip, created_by FROM cars WHERE id=%s AND channel_id=%s",
                (car_id, channel_id)
            )
            car_info = cur.fetchone()
            
            if not car_info:
                return False, "❌ Car not found.", []
            
            car_name, trip, car_owner = car_info
            
            # Check if user has permission to boot from this car
            if user_id != car_owner:
                return False, "❌ Only the car owner can remove people from their car.", []
            
            # Check which users are actually in the car and can be booted
            users_to_boot = []
            not_in_car = []
            cannot_boot_owner = []
            
            for target_user in target_user_ids:
                # Check if target user is the car owner (cannot boot owner)
                if target_user == car_owner:
                    cannot_boot_owner.append(target_user)
                    continue
                
                # Check if user is in this car
                cur.execute(
                    "SELECT 1 FROM car_members WHERE car_id=%s AND user_id=%s",
                    (car_id, target_user)
                )
                if cur.fetchone():
                    users_to_boot.append(target_user)
                else:
                    not_in_car.append(target_user)
            
            # Build error messages
            error_messages = []
            if not_in_car:
                mentions = [f"<@{uid}>" for uid in not_in_car]
                error_messages.append(f"Not in your car: {', '.join(mentions)}")
            
            if cannot_boot_owner:
                error_messages.append("Cannot remove the car owner")
            
            if not users_to_boot:
                if error_messages:
                    return False, f"❌ No users removed. {' | '.join(error_messages)}", []
                else:
                    return False, "❌ No valid users to remove.", []
            
            # Remove users from the car
            booted_users = []
            for target_user in users_to_boot:
                try:
                    cur.execute(
                        "DELETE FROM car_members WHERE car_id=%s AND user_id=%s",
                        (car_id, target_user)
                    )
                    booted_users.append(target_user)
                except Exception as e:
                    print(f"⚠️ boot_users_from_car unexpected error for user {target_user}: {e}")
                    continue
            
            conn.commit()
            
            # Build success message
            if booted_users:
                booted_mentions = [f"<@{uid}>" for uid in booted_users]
                success_msg = f"✅ You removed {', '.join(booted_mentions)} from your car (*{car_name}*)."
                
                if error_messages:
                    success_msg += f"\n\n⚠️ {' | '.join(error_messages)}"
                
                # Send DMs to booted users if client is provided
                if client:
                    for target_user in booted_users:
                        try:
                            client.chat_postMessage(
                                channel=target_user, 
                                text=f"🚗 You were removed from *{car_name}* on *{trip}* by <@{user_id}>."
                            )
                        except Exception as e:
                            print(f"⚠️ boot_users_from_car failed to send DM to {target_user}: {e}")
                
                # Post announcement
                if len(booted_users) == 1:
                    announcement = f":seat: <@{user_id}> removed <@{booted_users[0]}> from *{car_name}* on *{trip}*."
                else:
                    announcement = f":seat: <@{user_id}> removed {', '.join(booted_mentions)} from *{car_name}* on *{trip}*."
                
                post_announce(trip, channel_id, announcement)
                
                return True, success_msg, booted_users
            else:
                return False, "❌ No users were removed.", []
                
    except Exception as e:
        print(f"Error in boot_users_from_car: {e}")
        return False, f"❌ Error removing users: {str(e)}", []

def register_member_commands(bolt_app):
    """Register member management commands"""
    
    @bolt_app.command("/in")
    def cmd_in(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        user_mention = (command.get("text") or "").strip()
        
        # Debug: Log what we received
        print(f"🔍 /in command received text: '{user_mention}'")
        print(f"🔍 /in command text length: {len(user_mention)}")
        print(f"🔍 /in command text repr: {repr(user_mention)}")
        
        if not user_mention:
            return eph(respond, "Usage: `/in @car_owner` (mention the owner of the car you want to join)")
        
        # Extract user ID from mention - handle multiple formats (same logic as /add and /boot)
        target_car_owner = None
        
        # Format 1: Proper Slack mention <@U123456789> or <@U123456789|username>
        if user_mention.startswith("<@") and user_mention.endswith(">"):
            mention_content = user_mention[2:-1]
            if "|" in mention_content:
                target_car_owner = mention_content.split("|")[0]  # Take only the user ID part
            else:
                target_car_owner = mention_content
            print(f"✅ /in parsed Slack mention format: target_car_owner='{target_car_owner}'")
        
        # Format 2: Display name format - try to find user by display name or real name
        else:
            # Remove @ if present at the start
            search_name = user_mention.lstrip('@')
            print(f"🔍 /in trying to find user by name: '{search_name}'")
            
            try:
                from app import bolt_app
                # Get channel members to search through
                channel_members = get_channel_members(channel_id)
                print(f"🔍 /in found {len(channel_members)} channel members: {channel_members[:5]}...")  # Show first 5 for debugging
                
                if not channel_members:
                    print(f"❌ /in no channel members found - this might be a permissions issue")
                    return eph(respond, f":x: Could not retrieve channel members. Make sure the bot has proper permissions and is added to this channel.")
                
                # Collect potential matches with priority scoring
                potential_matches = []
                
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
                        
                        search_lower = search_name.lower()
                        
                        # Priority 1: Exact username match (highest priority)
                        if search_lower == name.lower():
                            potential_matches.append((member_id, 1, f"exact username: @{name}"))
                            continue
                            
                        # Priority 2: Exact match in display name or real name
                        if (search_lower == display_name.lower() or 
                            search_lower == real_name.lower()):
                            potential_matches.append((member_id, 2, f"exact name: {real_name}"))
                            continue
                            
                        # Priority 3: Username starts with search term (more restrictive)
                        if name.lower().startswith(search_lower):
                            potential_matches.append((member_id, 3, f"username starts with: @{name}"))
                            continue
                            
                        # Priority 4: Real name or display name starts with search term
                        if (real_name.lower().startswith(search_lower) or 
                            display_name.lower().startswith(search_lower)):
                            potential_matches.append((member_id, 4, f"name starts with: {real_name}"))
                            continue
                            
                        # Priority 5: Contains match (but only if search term is reasonably long to avoid false positives)
                        if len(search_lower) >= 4:  # Only do contains matching for longer search terms
                            if (search_lower in real_name.lower() or 
                                search_lower in display_name.lower()):
                                potential_matches.append((member_id, 5, f"name contains: {real_name}"))
                                continue
                            
                        # Priority 6: Partial word matching (most restrictive)
                        if len(search_lower) >= 3:  # Only for reasonably long search terms
                            name_parts = search_lower.replace('.', ' ').split()
                            for part in name_parts:
                                if len(part) >= 3:  # Only match parts that are at least 3 characters
                                    # Look for whole word matches, not just substrings
                                    real_name_words = real_name.lower().split()
                                    display_name_words = display_name.lower().split()
                                    username_parts = name.lower().replace('.', ' ').replace('_', ' ').split()
                                    
                                    if (part in real_name_words or 
                                        part in display_name_words or 
                                        part in username_parts):
                                        potential_matches.append((member_id, 6, f"partial word match '{part}': {real_name}"))
                                        break
                            
                    except Exception as e:
                        print(f"❌ /in error checking user {member_id}: {e}")
                        continue
                
                # Select the best match (lowest priority number = highest priority)
                if potential_matches:
                    # Sort by priority (lower number = higher priority)
                    potential_matches.sort(key=lambda x: x[1])
                    target_car_owner, priority, match_reason = potential_matches[0]
                    print(f"✅ /in selected best match: '{search_name}' -> {target_car_owner} ({match_reason})")
                    
                    # If we have multiple matches with the same priority, warn about ambiguity
                    if len(potential_matches) > 1 and potential_matches[0][1] == potential_matches[1][1]:
                        print(f"⚠️ /in found multiple matches with same priority for '{search_name}' - using first match")
                else:
                    target_car_owner = None
                        
            except Exception as e:
                print(f"❌ /in error searching for user by name: {e}")
        
        if not target_car_owner:
            return eph(respond, f":x: Could not find user '{user_mention}'. Please use @mention to select the car owner from the dropdown, or make sure they're in this channel.")
        
        user = command["user_id"]
        
        # Don't allow joining your own car
        if target_car_owner == user:
            return eph(respond, ":x: You can't request to join your own car.")
        
        # Get the active trip for this channel
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM trips WHERE channel_id=%s AND active=TRUE", (channel_id,))
            trip_row = cur.fetchone()
            
            if not trip_row:
                return eph(respond, ":x: No active trip in this channel. Create one with `/trip TripName` first.")
            
            trip = trip_row[0]
            
            # Check if the requesting user already has their own car in this trip
            cur.execute(
                "SELECT id, name FROM cars WHERE channel_id=%s AND trip=%s AND created_by=%s",
                (channel_id, trip, user)
            )
            user_car = cur.fetchone()
            
            if user_car:
                user_car_id, user_car_name = user_car
                return eph(respond, f":x: You already have your own car (*{user_car_name}*) on *{trip}*. Car owners cannot join other cars.")
            
            # Check if user has any pending join requests
            cur.execute(
                "SELECT jr.car_id, c.name, c.created_by FROM join_requests jr JOIN cars c ON jr.car_id = c.id WHERE jr.user_id=%s AND c.channel_id=%s AND c.trip=%s",
                (user, channel_id, trip)
            )
            pending_request = cur.fetchone()
            
            if pending_request:
                pending_car_id, pending_car_name, pending_car_owner = pending_request
                return eph(respond, f":x: You already have a pending request to join *{pending_car_name}* (owned by <@{pending_car_owner}>). You can only have one pending request at a time.")
            
            # Check if user is already in a car (for switching confirmation)
            cur.execute(
                "SELECT cm.car_id, c.name, c.created_by FROM car_members cm JOIN cars c ON cm.car_id = c.id WHERE cm.user_id=%s AND c.channel_id=%s AND c.trip=%s",
                (user, channel_id, trip)
            )
            current_car = cur.fetchone()
            
            # Find the car owned by the target user in this trip
            cur.execute(
                "SELECT id, name FROM cars WHERE channel_id=%s AND trip=%s AND created_by=%s",
                (channel_id, trip, target_car_owner)
            )
            car_row = cur.fetchone()
            
            if not car_row:
                return eph(respond, f":x: <@{target_car_owner}> doesn't have a car on *{trip}* that you can join.")
            
            car_id, car_name = car_row
            creator = target_car_owner
        
        # If user is already in a car, show confirmation dialog for switching
        if current_car:
            current_car_id, current_car_name, current_car_owner = current_car
            
            # Send confirmation dialog to the requesting user
            bolt_app.client.chat_postMessage(
                channel=user,
                text=f":warning: You are currently in *{current_car_name}* (owned by <@{current_car_owner}>). Do you want to switch to *{car_name}* (owned by <@{creator}>)?",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":warning: *You are currently in a car*\n:car: Current car: *{current_car_name}* (owned by <@{current_car_owner}>)\n:arrow_right: Requested car: *{car_name}* (owned by <@{creator}>)\n:round_pushpin: Trip: *{trip}*\n\nDo you want to switch cars?"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Yes, Switch Cars"},
                                "style": "primary",
                                "action_id": "confirm_car_switch",
                                "value": f"{car_id}:{user}:{current_car_id}"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Cancel"},
                                "style": "danger",
                                "action_id": "cancel_car_switch",
                                "value": f"{car_id}:{user}"
                            }
                        ]
                    }
                ]
            )
            return eph(respond, f":hourglass_flowing_sand: Confirmation sent to switch from *{current_car_name}* to *{car_name}*.")
        
        # User is not in a car, proceed with normal join request
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
            
            # Get car and trip info
            cur.execute("SELECT trip, name, created_by FROM cars WHERE id=%s", (car_id,))
            car_row = cur.fetchone()
            if not car_row:
                client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":x: Error: Car `{car_id}` no longer exists.", blocks=[])
                return
            
            trip, car_name, car_owner = car_row
            
            # Check if user is already in ANY car for this trip (for car switching)
            cur.execute(
                "SELECT cm.car_id, c.name, c.created_by FROM car_members cm JOIN cars c ON cm.car_id = c.id WHERE cm.user_id=%s AND c.trip=%s AND c.channel_id=%s",
                (user_to_add, trip, channel_id)
            )
            existing_car = cur.fetchone()
            
            old_car_info = None
            if existing_car:
                old_car_id, existing_car_name, existing_car_owner = existing_car
                old_car_info = (old_car_id, existing_car_name, existing_car_owner)
                
                # Remove user from their old car
                cur.execute("DELETE FROM car_members WHERE car_id=%s AND user_id=%s", (old_car_id, user_to_add))
                
                # Notify the old car owner that the user left
                client.chat_postMessage(
                    channel=existing_car_owner,
                    text=f":information_source: <@{user_to_add}> left your car *{existing_car_name}* to join another car on *{trip}*."
                )
                
                # Announce the departure from the old car
                post_announce(trip, channel_id, f":wave: <@{user_to_add}> left *{existing_car_name}* to switch cars on *{trip}*.")
            
            # Check if user is already in THIS car (shouldn't happen, but safety check)
            cur.execute("SELECT 1 FROM car_members WHERE car_id=%s AND user_id=%s", (car_id, user_to_add))
            if cur.fetchone():
                # Remove the join request since it's no longer valid
                cur.execute("DELETE FROM join_requests WHERE car_id=%s AND user_id=%s", (car_id, user_to_add))
                conn.commit()
                
                client.chat_update(
                    channel=body["channel"]["id"], 
                    ts=body["container"]["message_ts"], 
                    text=f":white_check_mark: <@{user_to_add}> is already in car `{car_id}`.", 
                    blocks=[]
                )
                return
            
            # Check if car has space
            cur.execute("SELECT seats FROM cars WHERE id=%s", (car_id,))
            total_seats = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM car_members WHERE car_id=%s", (car_id,))
            current_members = cur.fetchone()[0]
            
            if current_members >= total_seats:
                # Remove the join request since car is full
                cur.execute("DELETE FROM join_requests WHERE car_id=%s AND user_id=%s", (car_id, user_to_add))
                conn.commit()
                
                client.chat_update(
                    channel=body["channel"]["id"], 
                    ts=body["container"]["message_ts"], 
                    text=f":x: Cannot approve <@{user_to_add}> - car `{car_id}` is full ({current_members}/{total_seats} seats).", 
                    blocks=[]
                )
                client.chat_postMessage(
                    channel=user_to_add, 
                    text=f":x: Your request for *{car_name}* was denied because the car is now full ({current_members}/{total_seats} seats)."
                )
                return
            
            # All checks passed - add user to car
            cur.execute("DELETE FROM join_requests WHERE car_id=%s AND user_id=%s", (car_id, user_to_add))
            cur.execute("INSERT INTO car_members(car_id, user_id) VALUES(%s,%s)", (car_id, user_to_add))
            conn.commit()
            
        # Update messages based on whether this was a car switch or regular join
        if old_car_info:
            old_car_id, old_car_name, old_car_owner = old_car_info
            client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":white_check_mark: Approved <@{user_to_add}> for car `{car_id}` (switched from *{old_car_name}*).", blocks=[])
            client.chat_postMessage(channel=user_to_add, text=f":white_check_mark: You successfully switched from *{old_car_name}* to *{car_name}* on *{trip}*!")
            post_announce(trip, channel_id, f":arrows_counterclockwise: <@{user_to_add}> switched to car `{car_id}` (*{car_name}*) on *{trip}*.")
        else:
            client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":white_check_mark: Approved <@{user_to_add}> for car `{car_id}`.", blocks=[])
            client.chat_postMessage(channel=user_to_add, text=f":white_check_mark: You were approved for *{car_name}* on *{trip}*!")
            post_announce(trip, channel_id, f":seat: <@{user_to_add}> joined car `{car_id}` (*{car_name}*) on *{trip}*.")

    @bolt_app.action("dismiss_message")
    def act_dismiss(ack, respond):
        """Handle dismiss button clicks for auto-dismissing messages"""
        ack()
        # Delete the original message
        respond({"delete_original": True})

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

    @bolt_app.action("confirm_car_switch")
    def act_confirm_car_switch(ack, body, client):
        ack()
        car_id, user_id, current_car_id = body["actions"][0]["value"].split(":")
        car_id = int(car_id)
        current_car_id = int(current_car_id)
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Get car and trip info for the new car
            cur.execute("SELECT trip, name, created_by, channel_id FROM cars WHERE id=%s", (car_id,))
            car_row = cur.fetchone()
            if not car_row:
                client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":x: Error: Car `{car_id}` no longer exists.", blocks=[])
                return
            
            trip, car_name, car_owner, channel_id = car_row
            
            # Create the join request
            try:
                cur.execute(
                    "INSERT INTO join_requests(car_id, user_id) VALUES(%s,%s)",
                    (car_id, user_id)
                )
                conn.commit()
            except psycopg2.errors.UniqueViolation:
                client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":x: You already have a pending request for this car.", blocks=[])
                return
        
        # Send join request to the new car owner
        bolt_app.client.chat_postMessage(
            channel=car_owner,
            text=f":wave: <@{user_id}> wants to join your car `{car_id}` (*{car_name}*) on *{trip}*.",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":wave: *<@{user_id}> wants to join your car `{car_id}`*\n:car: Car: *{car_name}*\n:round_pushpin: Trip: *{trip}*\n:information_source: This user is switching from another car."
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
                            "value": f"{car_id}:{user_id}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Deny"},
                            "style": "danger",
                            "action_id": "deny_request",
                            "value": f"{car_id}:{user_id}"
                        }
                    ]
                }
            ]
        )
        
        client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":white_check_mark: Car switch request sent to <@{car_owner}>.", blocks=[])

    @bolt_app.action("cancel_car_switch")
    def act_cancel_car_switch(ack, body, client):
        ack()
        client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=":x: Car switch cancelled.", blocks=[])

    @bolt_app.command("/cancel")
    def cmd_cancel(ack, respond, command):
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
            
            # Check if user has any pending join requests
            cur.execute(
                "SELECT jr.car_id, c.name, c.created_by FROM join_requests jr JOIN cars c ON jr.car_id = c.id WHERE jr.user_id=%s AND c.channel_id=%s AND c.trip=%s",
                (user, channel_id, trip)
            )
            pending_request = cur.fetchone()
            
            if not pending_request:
                return auto_dismiss_eph(respond, ":x: You don't have any pending join requests to cancel.")
            
            car_id, car_name, car_owner = pending_request
            
            # Remove the join request
            cur.execute("DELETE FROM join_requests WHERE car_id=%s AND user_id=%s", (car_id, user))
            conn.commit()
        
        auto_dismiss_eph(respond, f":white_check_mark: Cancelled your request to join *{car_name}* (owned by <@{car_owner}>) on *{trip}*.", "Done")

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
                
                # Collect potential matches with priority scoring
                potential_matches = []
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
                        search_lower = search_name.lower()
                        
                        # Priority 1: Exact username match (highest priority)
                        if search_lower == name.lower():
                            potential_matches.append((member_id, 1, f"exact username: @{name}"))
                            continue
                            
                        # Priority 2: Exact match in display name or real name
                        if (search_lower == display_name.lower() or 
                            search_lower == real_name.lower()):
                            potential_matches.append((member_id, 2, f"exact name: {real_name}"))
                            continue
                            
                        # Priority 3: Username starts with search term (more restrictive)
                        if name.lower().startswith(search_lower):
                            potential_matches.append((member_id, 3, f"username starts with: @{name}"))
                            continue
                            
                        # Priority 4: Real name or display name starts with search term
                        if (real_name.lower().startswith(search_lower) or 
                            display_name.lower().startswith(search_lower)):
                            potential_matches.append((member_id, 4, f"name starts with: {real_name}"))
                            continue
                            
                        # Priority 5: Contains match (but only if search term is reasonably long to avoid false positives)
                        if len(search_lower) >= 4:  # Only do contains matching for longer search terms
                            if (search_lower in real_name.lower() or 
                                search_lower in display_name.lower()):
                                potential_matches.append((member_id, 5, f"name contains: {real_name}"))
                                continue
                            
                        # Priority 6: Partial word matching (most restrictive)
                        if len(search_lower) >= 3:  # Only for reasonably long search terms
                            name_parts = search_lower.replace('.', ' ').split()
                            for part in name_parts:
                                if len(part) >= 3:  # Only match parts that are at least 3 characters
                                    # Look for whole word matches, not just substrings
                                    real_name_words = real_name.lower().split()
                                    display_name_words = display_name.lower().split()
                                    username_parts = name.lower().replace('.', ' ').replace('_', ' ').split()
                                    
                                    if (part in real_name_words or 
                                        part in display_name_words or 
                                        part in username_parts):
                                        potential_matches.append((member_id, 6, f"partial word match '{part}': {real_name}"))
                                        break
                            
                    except Exception as e:
                        print(f"❌ /boot error checking user {member_id}: {e}")
                        continue
                
                # Select the best match (lowest priority number = highest priority)
                if potential_matches:
                    # Sort by priority (lower number = higher priority)
                    potential_matches.sort(key=lambda x: x[1])
                    target_user, priority, match_reason = potential_matches[0]
                    print(f"✅ /boot selected best match: '{search_name}' -> {target_user} ({match_reason})")
                    
                    # If we have multiple matches with the same priority, warn about ambiguity
                    if len(potential_matches) > 1 and potential_matches[0][1] == potential_matches[1][1]:
                        print(f"⚠️ /boot found multiple matches with same priority for '{search_name}' - using first match")
                else:
                    target_user = None
                    
                print(f"🔍 /boot checked users: {found_users[:10]}...")  # Show first 10 users we found
                        
            except Exception as e:
                print(f"❌ /boot error searching for user by name: {e}")
        
        if not target_user:
            return eph(respond, f":x: Could not find user '{user_mention}'. Please use @mention to select the user from the dropdown, or make sure they're in this channel.")
        
        user = command["user_id"]
        
        # Prevent users from booting themselves
        if target_user == user:
            return eph(respond, ":x: You cannot boot yourself from your own car. Use `/out` to leave your car instead.")
        
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
        
        user_mentions_text = (command.get("text") or "").strip()
        
        # Debug: Log what we received
        print(f"🔍 /add command received text: '{user_mentions_text}'")
        print(f"🔍 /add command text length: {len(user_mentions_text)}")
        print(f"🔍 /add command text repr: {repr(user_mentions_text)}")
        
        if not user_mentions_text:
            return eph(respond, "Usage: `/add @user1 @user2 @user3` (can add multiple users at once)")
        
        # Parse multiple mentions - split by spaces and handle both formats
        import re
        
        # Find all Slack mentions in format <@U123456789> or <@U123456789|username>
        slack_mentions = re.findall(r'<@([^>]+)>', user_mentions_text)
        
        # Find all @username mentions (not in <> format)
        text_without_slack_mentions = re.sub(r'<@[^>]+>', '', user_mentions_text)
        text_mentions = re.findall(r'@([\w\.\-]+)', text_without_slack_mentions)
        
        print(f"🔍 /add found {len(slack_mentions)} Slack mentions: {slack_mentions}")
        print(f"🔍 /add found {len(text_mentions)} text mentions: {text_mentions}")
        
        def find_user_by_name(search_name):
            """Helper function to find a user by display name or username using priority-based matching"""
            try:
                from app import bolt_app
                channel_members = get_channel_members(channel_id)
                
                if not channel_members:
                    return None
                
                # Collect potential matches with priority scoring
                potential_matches = []
                
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
                        
                        search_lower = search_name.lower()
                        
                        # Priority 1: Exact username match (highest priority)
                        if search_lower == name.lower():
                            potential_matches.append((member_id, 1, f"exact username: @{name}"))
                            continue
                            
                        # Priority 2: Exact match in display name or real name
                        if (search_lower == display_name.lower() or 
                            search_lower == real_name.lower()):
                            potential_matches.append((member_id, 2, f"exact name: {real_name}"))
                            continue
                            
                        # Priority 3: Username starts with search term (more restrictive)
                        if name.lower().startswith(search_lower):
                            potential_matches.append((member_id, 3, f"username starts with: @{name}"))
                            continue
                            
                        # Priority 4: Real name or display name starts with search term
                        if (real_name.lower().startswith(search_lower) or 
                            display_name.lower().startswith(search_lower)):
                            potential_matches.append((member_id, 4, f"name starts with: {real_name}"))
                            continue
                            
                        # Priority 5: Contains match (but only if search term is reasonably long to avoid false positives)
                        if len(search_lower) >= 4:  # Only do contains matching for longer search terms
                            if (search_lower in real_name.lower() or 
                                search_lower in display_name.lower()):
                                potential_matches.append((member_id, 5, f"name contains: {real_name}"))
                                continue
                            
                        # Priority 6: Partial word matching (most restrictive)
                        if len(search_lower) >= 3:  # Only for reasonably long search terms
                            name_parts = search_lower.replace('.', ' ').split()
                            for part in name_parts:
                                if len(part) >= 3:  # Only match parts that are at least 3 characters
                                    # Look for whole word matches, not just substrings
                                    real_name_words = real_name.lower().split()
                                    display_name_words = display_name.lower().split()
                                    username_parts = name.lower().replace('.', ' ').replace('_', ' ').split()
                                    
                                    if (part in real_name_words or 
                                        part in display_name_words or 
                                        part in username_parts):
                                        potential_matches.append((member_id, 6, f"partial word match '{part}': {real_name}"))
                                        break
                                
                    except Exception as e:
                        print(f"❌ /add error checking user {member_id}: {e}")
                        continue
                
                # Select the best match (lowest priority number = highest priority)
                if potential_matches:
                    # Sort by priority (lower number = higher priority)
                    potential_matches.sort(key=lambda x: x[1])
                    target_user, priority, match_reason = potential_matches[0]
                    print(f"✅ /add selected best match: '{search_name}' -> {target_user} ({match_reason})")
                    
                    # If we have multiple matches with the same priority, warn about ambiguity
                    if len(potential_matches) > 1 and potential_matches[0][1] == potential_matches[1][1]:
                        print(f"⚠️ /add found multiple matches with same priority for '{search_name}' - using first match")
                    
                    return target_user
                else:
                    return None
                        
            except Exception as e:
                print(f"❌ /add error searching for user by name: {e}")
            
            return None
        
        # Process all mentions and collect target users
        target_users = []
        failed_mentions = []
        
        # Process Slack mentions
        for mention in slack_mentions:
            if "|" in mention:
                user_id = mention.split("|")[0]  # Take only the user ID part
            else:
                user_id = mention
            target_users.append(user_id)
            print(f"✅ /add parsed Slack mention: {mention} -> {user_id}")
        
        # Process text mentions
        for mention in text_mentions:
            user_id = find_user_by_name(mention)
            if user_id:
                target_users.append(user_id)
            else:
                failed_mentions.append(f"@{mention}")
        
        # Remove duplicates while preserving order
        unique_target_users = []
        seen = set()
        for user_id in target_users:
            if user_id not in seen:
                unique_target_users.append(user_id)
                seen.add(user_id)
        
        target_users = unique_target_users
        
        if failed_mentions:
            return eph(respond, f":x: Could not find users: {', '.join(failed_mentions)}. Please use @mention to select users from the dropdown, or make sure they're in this channel.")
        
        if not target_users:
            return eph(respond, ":x: No valid users found to add. Please mention users with @username format.")
        
        user = command["user_id"]
        
        # Remove the command user from target_users if they tried to add themselves
        if user in target_users:
            target_users.remove(user)
            print(f"⚠️ /add removed command user {user} from target list (can't add yourself)")
        
        if not target_users:
            return eph(respond, ":x: No valid users to add (you can't add yourself to your own car).")
        
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
            
            # Get current members count
            cur.execute("SELECT COUNT(*) FROM car_members WHERE car_id=%s", (car_id,))
            current_members = cur.fetchone()[0]
            
            # Check if we have enough space for all users
            available_seats = total_seats - current_members
            if len(target_users) > available_seats:
                return eph(respond, f":x: Your car (*{car_name}*) only has {available_seats} available seats, but you're trying to add {len(target_users)} users. Use `/update` to increase seats or `/boot` to remove someone first.")
            
            # Check each target user for conflicts and duplicates
            users_to_add = []
            already_in_car = []
            already_in_other_cars = []
            
            for target_user in target_users:
                # Check if user is already in this car
                cur.execute(
                    "SELECT 1 FROM car_members WHERE car_id=%s AND user_id=%s",
                    (car_id, target_user)
                )
                if cur.fetchone():
                    already_in_car.append(target_user)
                    continue
                
                # Check if user is already in ANY other car for this trip
                cur.execute(
                    "SELECT c.name, c.created_by FROM car_members cm JOIN cars c ON cm.car_id = c.id WHERE cm.user_id=%s AND c.trip=%s AND c.channel_id=%s",
                    (target_user, trip, channel_id)
                )
                existing_car = cur.fetchone()
                
                if existing_car:
                    existing_car_name, existing_car_owner = existing_car
                    already_in_other_cars.append((target_user, existing_car_name, existing_car_owner))
                    continue
                
                users_to_add.append(target_user)
            
            # Build error messages for conflicts
            error_messages = []
            if already_in_car:
                mentions = [f"<@{uid}>" for uid in already_in_car]
                error_messages.append(f"Already in your car: {', '.join(mentions)}")
            
            if already_in_other_cars:
                conflicts = [f"<@{uid}> (in *{car_name}* by <@{owner}>)" for uid, car_name, owner in already_in_other_cars]
                error_messages.append(f"Already in other cars: {', '.join(conflicts)}")
            
            if not users_to_add:
                if error_messages:
                    return eph(respond, f":x: No users added. {' | '.join(error_messages)}")
                else:
                    return eph(respond, ":x: No valid users to add.")
            
            # Add all valid users to the car
            added_users = []
            for target_user in users_to_add:
                try:
                    cur.execute(
                        "INSERT INTO car_members(car_id, user_id) VALUES(%s, %s)",
                        (car_id, target_user)
                    )
                    added_users.append(target_user)
                except psycopg2.errors.UniqueViolation:
                    # This shouldn't happen since we checked above, but just in case
                    print(f"⚠️ /add unexpected duplicate for user {target_user}")
                    continue
            
            conn.commit()
        
        # Send success message
        if added_users:
            added_mentions = [f"<@{uid}>" for uid in added_users]
            success_msg = f":white_check_mark: You added {', '.join(added_mentions)} to your car (*{car_name}*)."
            
            if error_messages:
                success_msg += f"\n\n⚠️ {' | '.join(error_messages)}"
            
            eph(respond, success_msg)
            
            # Send DMs to added users
            for target_user in added_users:
                try:
                    bolt_app.client.chat_postMessage(
                        channel=target_user, 
                        text=f":car: You were added to *{car_name}* on *{trip}* by <@{user}>."
                    )
                except Exception as e:
                    print(f"⚠️ /add failed to send DM to {target_user}: {e}")
            
            # Post announcement
            if len(added_users) == 1:
                announcement = f":seat: <@{user}> added <@{added_users[0]}> to *{car_name}* on *{trip}*."
            else:
                announcement = f":seat: <@{user}> added {', '.join(added_mentions)} to *{car_name}* on *{trip}*."
            
            post_announce(trip, channel_id, announcement)
