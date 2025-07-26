"""
Trip management commands for the carpool bot
"""
import psycopg2
from config.database import get_conn
from utils.helpers import eph, get_channel_members
from utils.channel_guard import check_bot_channel_access

def is_channel_active(channel_id):
    """Check if a channel is still active (not archived/deleted)"""
    try:
        from app import bolt_app as app
        channel_info = app.client.conversations_info(channel=channel_id)
        if channel_info["ok"]:
            channel = channel_info["channel"]
            # Channel is inactive if it's archived or deleted
            is_archived = channel.get("is_archived", False)
            return not is_archived
        else:
            # If we can't get channel info, assume it's deleted/inaccessible
            return False
    except Exception:
        # Any exception means we can't access the channel
        return False

def register_trip_commands(bolt_app):
    """Register trip management commands"""
    
    @bolt_app.command("/trip")
    def cmd_trip(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        trip = (command.get("text") or "").strip()
        if not trip:
            return eph(respond, "Usage: `/trip TripName`")
        user = command["user_id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # First check if trip name already exists ANYWHERE (global uniqueness)
            cur.execute("SELECT channel_id, created_by FROM trips WHERE name=%s", (trip,))
            existing_trip = cur.fetchone()
            
            if existing_trip:
                existing_channel_id, existing_creator = existing_trip
                if existing_channel_id == channel_id:
                    # Trip exists in this channel - handle replacement logic
                    pass  # Continue to existing replacement logic below
                else:
                    # Trip exists in a different channel - check if that channel is still active
                    if is_channel_active(existing_channel_id):
                        # Original channel is still active - not allowed to reuse name
                        return eph(respond, f":x: Trip name '*{trip}*' is already used in <#{existing_channel_id}> by <@{existing_creator}>. Please choose a different name.")
                    else:
                        # Original channel is archived/deleted - allow reuse by deleting old trip
                        print(f"🗑️ Cleaning up trip '{trip}' from inactive channel {existing_channel_id}")
                        
                        # Cascade delete the old trip and all its data
                        cur.execute(
                            """
                            DELETE FROM car_members 
                            WHERE car_id IN (SELECT id FROM cars WHERE trip = %s)
                            """,
                            (trip,)
                        )
                        cur.execute(
                            """
                            DELETE FROM join_requests 
                            WHERE car_id IN (SELECT id FROM cars WHERE trip = %s)
                            """,
                            (trip,)
                        )
                        cur.execute("DELETE FROM cars WHERE trip = %s", (trip,))
                        cur.execute("DELETE FROM trips WHERE name = %s", (trip,))
                        conn.commit()
                        
                        print(f"✅ Cleaned up old trip '{trip}' from inactive channel")
            
            # Check if this trip name already exists
            cur.execute("SELECT name, channel_id, created_by, active FROM trips WHERE name=%s", (trip,))
            existing_trip_with_name = cur.fetchone()
            
            if existing_trip_with_name:
                existing_name, existing_channel, existing_creator, is_active = existing_trip_with_name
                if existing_channel != channel_id:
                    # Trip name exists in different channel - check if that channel is active
                    if is_channel_active(existing_channel):
                        return eph(respond, f":x: Trip name '*{trip}*' is already used in <#{existing_channel}> by <@{existing_creator}>. Please choose a different name.")
                    else:
                        # Original channel is inactive - deactivate the old trip
                        cur.execute("UPDATE trips SET active = FALSE WHERE name = %s", (trip,))
                        print(f"🔄 Deactivated trip '{trip}' from inactive channel {existing_channel}")
            
            # Check if there's currently an active trip in this channel
            cur.execute("SELECT name, created_by FROM trips WHERE channel_id=%s AND active=TRUE", (channel_id,))
            current_active_trip = cur.fetchone()
            
            if current_active_trip:
                current_trip_name, current_creator = current_active_trip
                
                # If trying to activate the same trip that's already active
                if current_trip_name == trip:
                    return eph(respond, f":information_source: Trip *{trip}* is already active in this channel.")
                
                # Check if user can switch the active trip
                if current_creator != user:
                    # Check if original creator is still in the channel
                    channel_members = get_channel_members(channel_id)
                    if current_creator in channel_members:
                        # Original creator still in channel - need approval (implement approval flow)
                        return eph(respond, f":x: Cannot switch from *{current_trip_name}* to *{trip}*. Only the trip creator (<@{current_creator}>) can change the active trip, or they must leave the channel first.")
                
                # Deactivate the current trip
                cur.execute("UPDATE trips SET active = FALSE WHERE channel_id=%s AND active=TRUE", (channel_id,))
                print(f"🔄 Deactivated trip '{current_trip_name}' in channel {channel_id}")
            
            # Try to activate existing trip or create new one
            cur.execute("SELECT name FROM trips WHERE name=%s", (trip,))
            trip_exists = cur.fetchone()
            
            if trip_exists:
                # Trip exists - activate it for this channel
                cur.execute(
                    "UPDATE trips SET channel_id=%s, active=TRUE, created_at=CURRENT_TIMESTAMP WHERE name=%s",
                    (channel_id, trip)
                )
                conn.commit()
                eph(respond, f":round_pushpin: Trip *{trip}* activated for this channel.")
            else:
                # Create new trip
                try:
                    cur.execute(
                        "INSERT INTO trips(name, channel_id, created_by, active) VALUES(%s,%s,%s,TRUE)",
                        (trip, channel_id, user)
                    )
                    conn.commit()
                    eph(respond, f":round_pushpin: Trip *{trip}* created and activated for this channel.")
                except psycopg2.errors.UniqueViolation:
                    # Trip name already exists globally - this shouldn't happen if our logic above is correct
                    # But handle it gracefully by trying to activate the existing trip
                    conn.rollback()
                    cur.execute(
                        "UPDATE trips SET channel_id=%s, active=TRUE, created_at=CURRENT_TIMESTAMP WHERE name=%s",
                        (channel_id, trip)
                    )
                    conn.commit()
                    eph(respond, f":round_pushpin: Trip *{trip}* activated for this channel (recovered from duplicate key error).")

    @bolt_app.action("approve_trip_overwrite")
    def act_approve_trip_overwrite(ack, body, client):
        ack()
        channel_id, requesting_user, new_trip_name = body["actions"][0]["value"].split(":")
        approving_user = body["user"]["id"]
        
        # Update the trip in the database
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE trips SET name=%s, created_by=%s, created_at=CURRENT_TIMESTAMP WHERE channel_id=%s",
                (new_trip_name, requesting_user, channel_id)
            )
            conn.commit()
        
        # Update the approval message
        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["container"]["message_ts"],
            text=f":white_check_mark: You approved the trip overwrite.",
            blocks=[]
        )
        
        # Notify the requesting user
        client.chat_postMessage(
            channel=requesting_user,
            text=f":white_check_mark: <@{approving_user}> approved your trip *{new_trip_name}* in <#{channel_id}>. The trip has been updated!"
        )
        
        # Announce to the channel
        client.chat_postMessage(
            channel=channel_id,
            text=f":round_pushpin: Trip *{new_trip_name}* was approved and updated by <@{requesting_user}> (approved by <@{approving_user}>)."
        )

    @bolt_app.action("deny_trip_overwrite")
    def act_deny_trip_overwrite(ack, body, client):
        ack()
        channel_id, requesting_user, new_trip_name = body["actions"][0]["value"].split(":")
        denying_user = body["user"]["id"]
        
        # Update the approval message
        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["container"]["message_ts"],
            text=f":x: You denied the trip overwrite.",
            blocks=[]
        )
        
        # Notify the requesting user
        client.chat_postMessage(
            channel=requesting_user,
            text=f":x: <@{denying_user}> denied your request to replace their trip with *{new_trip_name}* in <#{channel_id}>."
        )
    
    @bolt_app.command("/deletetrip")
    def cmd_deletetrip(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        trip_name = (command.get("text") or "").strip()
        if not trip_name:
            return eph(respond, "Usage: `/deletetrip TripName`")
        
        user = command["user_id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Check if trip exists globally and user is the creator (since trip names are globally unique)
            cur.execute(
                "SELECT created_by, channel_id FROM trips WHERE name=%s",
                (trip_name,)
            )
            row = cur.fetchone()
            
            if not row:
                return eph(respond, f":x: Trip '*{trip_name}*' does not exist.")
            
            trip_creator, trip_channel_id = row
            
            if trip_creator != user:
                return eph(respond, f":x: Only the trip creator can delete '*{trip_name}*'.")
            
            # Check if there are any cars on this trip for informational purposes
            cur.execute(
                "SELECT COUNT(*) FROM cars WHERE trip=%s",
                (trip_name,)
            )
            car_count = cur.fetchone()[0]
        
        # Create appropriate warning message based on car count
        if car_count > 0:
            warning_text = f":warning: Are you sure you want to delete trip '*{trip_name}*'? This will also delete **{car_count} car(s)** and all their members. This action cannot be undone."
        else:
            warning_text = f":warning: Are you sure you want to delete trip '*{trip_name}*'? This action cannot be undone."
        
        # Send confirmation prompt for trip deletion
        respond({
            "text": warning_text,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": warning_text
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Yes, Delete Trip"},
                            "style": "danger",
                            "action_id": "confirm_delete_trip",
                            "value": f"{trip_name}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "action_id": "cancel_delete_trip",
                            "value": f"{trip_name}"
                        }
                    ]
                }
            ]
        })

    @bolt_app.action("confirm_delete_trip")
    def handle_confirm_delete_trip(ack, body, client, respond):
        ack()
        
        # Extract trip name from the action value
        trip_name = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Check if user is the trip creator (global lookup)
            cur.execute(
                "SELECT created_by, channel_id FROM trips WHERE name=%s",
                (trip_name,)
            )
            row = cur.fetchone()
            
            if not row:
                try:
                    client.chat_update(
                        channel=body["channel"]["id"], 
                        ts=body["container"]["message_ts"], 
                        text=f":x: Trip '*{trip_name}*' not found.", 
                        blocks=[]
                    )
                except Exception:
                    # Fallback to respond if message update fails
                    respond(f":x: Trip '*{trip_name}*' not found.")
                return
            
            trip_creator, trip_channel_id = row
            
            if trip_creator != user_id:
                try:
                    client.chat_update(
                        channel=body["channel"]["id"], 
                        ts=body["container"]["message_ts"], 
                        text=f":x: Only the trip creator can delete '*{trip_name}*'.", 
                        blocks=[]
                    )
                except Exception:
                    # Fallback to respond if message update fails
                    respond(f":x: Only the trip creator can delete '*{trip_name}*'.")
                return
            
            # Get information about cars for the deletion announcement
            cur.execute(
                "SELECT COUNT(*) FROM cars WHERE trip=%s",
                (trip_name,)
            )
            car_count = cur.fetchone()[0]
            
            # Get total member count across all cars for the announcement
            cur.execute(
                """
                SELECT COUNT(*) FROM car_members cm
                JOIN cars c ON cm.car_id = c.id
                WHERE c.trip = %s
                """,
                (trip_name,)
            )
            member_count = cur.fetchone()[0]
            
            # Cascade delete: Remove all related data in correct order
            # 1. Delete all car members
            cur.execute(
                """
                DELETE FROM car_members 
                WHERE car_id IN (SELECT id FROM cars WHERE trip = %s)
                """,
                (trip_name,)
            )
            
            # 2. Delete all join requests for cars in this trip
            cur.execute(
                """
                DELETE FROM join_requests 
                WHERE car_id IN (SELECT id FROM cars WHERE trip = %s)
                """,
                (trip_name,)
            )
            
            # 3. Delete all cars
            cur.execute(
                "DELETE FROM cars WHERE trip = %s",
                (trip_name,)
            )
            
            # 4. Finally delete the trip
            cur.execute(
                "DELETE FROM trips WHERE name = %s",
                (trip_name,)
            )
            conn.commit()
        
        # Create appropriate success message based on what was deleted
        if car_count > 0:
            success_text = f":white_check_mark: Trip '*{trip_name}*' has been deleted along with {car_count} car(s) and {member_count} membership(s)."
        else:
            success_text = f":white_check_mark: Trip '*{trip_name}*' has been deleted."
        
        # Update the message to show completion with error handling
        try:
            client.chat_update(
                channel=body["channel"]["id"], 
                ts=body["container"]["message_ts"], 
                text=success_text, 
                blocks=[]
            )
        except Exception:
            # Fallback to respond if message update fails
            respond(success_text)
        
        # Post announcement to the trip's original channel if it still exists
        try:
            from app import bolt_app as app
            app.client.chat_postMessage(
                channel=trip_channel_id,
                text=f":boom: Trip '*{trip_name}*' was deleted by <@{user_id}> along with all its cars and members."
            )
        except Exception:
            # Channel might be archived/deleted, which is fine
            pass

    @bolt_app.action("cancel_delete_trip")
    def handle_cancel_delete_trip(ack, body, client, respond):
        ack()
        try:
            client.chat_update(
                channel=body["channel"]["id"], 
                ts=body["container"]["message_ts"], 
                text=":information_source: Trip deletion cancelled.", 
                blocks=[]
            )
        except Exception:
            # Fallback to respond if message update fails
            respond(":information_source: Trip deletion cancelled.")

