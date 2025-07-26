"""
Trip management commands for the carpool bot
"""
import psycopg2
from config.database import get_conn
from utils.helpers import eph, get_channel_members

def register_trip_commands(bolt_app):
    """Register trip management commands"""
    
    @bolt_app.command("/trip")
    def cmd_trip(ack, respond, command):
        ack()
        trip = (command.get("text") or "").strip()
        if not trip:
            return eph(respond, "Usage: `/trip TripName`")
        user = command["user_id"]
        channel_id = command["channel_id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
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

