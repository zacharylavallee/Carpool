"""
Member management commands for the carpool bot
"""
import psycopg2
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, post_announce
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
        if not user_mention:
            return eph(respond, "Usage: `/boot @user`")
        
        # Extract user ID from mention
        if not user_mention.startswith("<@") or not user_mention.endswith(">"):
            return eph(respond, ":x: Please mention a user like @username")
        target_user = user_mention[2:-1]  # Remove <@ and >
        
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
