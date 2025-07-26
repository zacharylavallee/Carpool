"""
Member management commands for the carpool bot
"""
import psycopg2
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, post_announce

def register_member_commands(bolt_app):
    """Register member management commands"""
    
    @bolt_app.command("/in")
    def cmd_in(ack, respond, command):
        ack()
        car_id_str = (command.get("text") or "").strip()
        if not car_id_str:
            return eph(respond, "Usage: `/in CarID`")
        try:
            car_id = int(car_id_str)
        except ValueError:
            return eph(respond, ":x: CarID must be a number.")
        user = command["user_id"]
        channel_id = command["channel_id"]
        
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
        car_id_str = (command.get("text") or "").strip()
        if not car_id_str:
            return eph(respond, "Usage: `/out CarID`")
        try:
            car_id = int(car_id_str)
        except ValueError:
            return eph(respond, ":x: CarID must be a number.")
        user = command["user_id"]
        channel_id = command["channel_id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT trip FROM cars WHERE id=%s", (car_id,))
            row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Car `{car_id}` does not exist.")
        trip = row[0]
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM car_members WHERE car_id=%s AND user_id=%s", (car_id, user))
            conn.commit()
        eph(respond, f":white_check_mark: You left car `{car_id}`.")
        post_announce(trip, channel_id, f":dash: <@{user}> left car `{car_id}` on *{trip}*.")

    @bolt_app.command("/boot")
    def cmd_boot(ack, respond, command):
        ack()
        parts = (command.get("text") or "").split()
        if len(parts) != 2:
            return eph(respond, "Usage: `/boot CarID @user`")
        try:
            car_id = int(parts[0])
        except ValueError:
            return eph(respond, ":x: CarID must be a number.")
        target_user = parts[1].strip("<@>")
        user = command["user_id"]
        channel_id = command["channel_id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT created_by, trip FROM cars WHERE id=%s", (car_id,))
            row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Car `{car_id}` does not exist.")
        if row[0] != user:
            return eph(respond, ":x: Only the car creator can remove members.")
        trip = row[1]
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM car_members WHERE car_id=%s AND user_id=%s", (car_id, target_user))
            conn.commit()
        eph(respond, f":white_check_mark: You removed <@{target_user}> from car `{car_id}`.")
        bolt_app.client.chat_postMessage(channel=target_user, text=f":boot: You were removed from car `{car_id}` on *{trip}*.")
        post_announce(trip, channel_id, f":boot: <@{user}> removed <@{target_user}> from car `{car_id}` on *{trip}*.")
