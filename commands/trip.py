"""
Trip management commands for the carpool bot
"""
import psycopg2
from config.database import get_conn
from utils.helpers import eph, get_channel_members
from utils.channel_guard import check_bot_channel_access

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
                    # Trip exists in a different channel - not allowed
                    return eph(respond, f":x: Trip name '*{trip}*' is already used in <#{existing_channel_id}> by <@{existing_creator}>. Please choose a different name.")
            
            try:
                # Try to insert new trip (will fail if channel already has a trip)
                cur.execute(
                    "INSERT INTO trips(name, channel_id, created_by) VALUES(%s,%s,%s)",
                    (trip, channel_id, user)
                )
                conn.commit()
                eph(respond, f":round_pushpin: Trip *{trip}* created for this channel.")
            except psycopg2.errors.UniqueViolation:
                # Rollback the failed transaction
                conn.rollback()
                
                # Check if there's an existing trip and who created it
                cur.execute("SELECT name, created_by FROM trips WHERE channel_id=%s", (channel_id,))
                existing_trip = cur.fetchone()
                if not existing_trip:
                    return eph(respond, ":x: Unexpected error - no existing trip found.")
                
                existing_trip_name, original_creator = existing_trip
                
                # If the same user is trying to update their own trip, allow it
                if original_creator == user:
                    cur.execute(
                        "UPDATE trips SET name=%s, created_at=CURRENT_TIMESTAMP WHERE channel_id=%s",
                        (trip, channel_id)
                    )
                    conn.commit()
                    return eph(respond, f":round_pushpin: Trip *{trip}* updated (you created the original trip).")
                
                # Check if original creator is still in the channel
                channel_members = get_channel_members(channel_id)
                if original_creator not in channel_members:
                    # Original creator is no longer in channel, allow overwrite
                    cur.execute(
                        "UPDATE trips SET name=%s, created_by=%s, created_at=CURRENT_TIMESTAMP WHERE channel_id=%s",
                        (trip, user, channel_id)
                    )
                    conn.commit()
                    return eph(respond, f":round_pushpin: Trip *{trip}* replaced the existing trip (original creator no longer in channel).")
                
                # Original creator is still in channel, send approval request
                from app import bolt_app as app
                try:
                    app.client.chat_postMessage(
                        channel=original_creator,
                        text=f":warning: <@{user}> wants to replace your trip *{existing_trip_name}* with *{trip}* in <#{channel_id}>.",
                        blocks=[
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f":warning: <@{user}> wants to replace your trip *{existing_trip_name}* with *{trip}* in <#{channel_id}>."
                                }
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": {"type": "plain_text", "text": "Approve"},
                                        "style": "primary",
                                        "action_id": "approve_trip_overwrite",
                                        "value": f"{channel_id}:{user}:{trip}"
                                    },
                                    {
                                        "type": "button",
                                        "text": {"type": "plain_text", "text": "Deny"},
                                        "style": "danger",
                                        "action_id": "deny_trip_overwrite",
                                        "value": f"{channel_id}:{user}:{trip}"
                                    }
                                ]
                            }
                        ]
                    )
                    eph(respond, f":hourglass_flowing_sand: Approval request sent to <@{original_creator}> (original trip creator). They need to approve before *{trip}* can replace *{existing_trip_name}*.")
                except Exception as e:
                    # If we can't send DM, fall back to allowing the overwrite
                    cur.execute(
                        "UPDATE trips SET name=%s, created_by=%s, created_at=CURRENT_TIMESTAMP WHERE channel_id=%s",
                        (trip, user, channel_id)
                    )
                    conn.commit()
                    eph(respond, f":round_pushpin: Trip *{trip}* replaced the existing trip (couldn't send approval request).")

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
            
            # Check if there are any cars on this trip
            cur.execute(
                "SELECT COUNT(*) FROM cars WHERE trip=%s",
                (trip_name,)
            )
            car_count = cur.fetchone()[0]
            
            if car_count > 0:
                return eph(respond, f":x: Cannot delete trip '*{trip_name}*' - it has {car_count} car(s). Delete all cars first.")
        
        # Send confirmation prompt for trip deletion
        respond({
            "text": f":warning: Are you sure you want to delete trip '*{trip_name}*'?",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":warning: Are you sure you want to delete trip '*{trip_name}*'? This action cannot be undone."
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
            
            # Check if trip has any cars
            cur.execute(
                "SELECT COUNT(*) FROM cars WHERE trip=%s",
                (trip_name,)
            )
            car_count = cur.fetchone()[0]
            
            if car_count > 0:
                try:
                    client.chat_update(
                        channel=body["channel"]["id"], 
                        ts=body["container"]["message_ts"], 
                        text=f":x: Cannot delete trip '*{trip_name}*' - it has {car_count} car(s). Delete all cars first.", 
                        blocks=[]
                    )
                except Exception:
                    # Fallback to respond if message update fails
                    respond(f":x: Cannot delete trip '*{trip_name}*' - it has {car_count} car(s). Delete all cars first.")
                return
            
            # Delete the trip
            cur.execute(
                "DELETE FROM trips WHERE name=%s",
                (trip_name,)
            )
            conn.commit()
        
        # Update the message to show completion with error handling
        try:
            client.chat_update(
                channel=body["channel"]["id"], 
                ts=body["container"]["message_ts"], 
                text=f":white_check_mark: Trip '*{trip_name}*' has been deleted.", 
                blocks=[]
            )
        except Exception:
            # Fallback to respond if message update fails
            respond(f":white_check_mark: Trip '*{trip_name}*' has been deleted.")

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

