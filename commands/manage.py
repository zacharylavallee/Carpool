"""
Car management commands for the carpool bot (update/remove cars)
"""
import psycopg2
from config.database import get_conn
from utils.helpers import eph, post_announce

def register_manage_commands(bolt_app):
    """Register car management commands"""
    
    @bolt_app.command("/update")
    def cmd_update(ack, respond, command):
        ack()
        parts = (command.get("text") or "").split()
        if len(parts) != 2 or not parts[1].startswith("seats="):
            return eph(respond, "Usage: `/update CarID seats=X` (e.g., `/update 1 seats=5`)") 
        try:
            car_id = int(parts[0])
            new_seats = int(parts[1].split("=")[1])
        except (ValueError, IndexError):
            return eph(respond, ":x: Invalid format. Use `/update CarID seats=X`")
        user = command["user_id"]
        channel_id = command["channel_id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT created_by, trip FROM cars WHERE id=%s", (car_id,))
            row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Car `{car_id}` does not exist.")
        if row[0] != user:
            return eph(respond, ":x: Only the car creator can update it.")
        trip = row[1]
        
        # Check if new seat count is valid (not less than current members)
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM car_members WHERE car_id=%s", (car_id,))
            current_members = cur.fetchone()[0]
        if new_seats < current_members:
            return eph(respond, f":x: Cannot reduce seats to {new_seats}. Car has {current_members} members.")
        
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE cars SET seats=%s WHERE id=%s", (new_seats, car_id))
            conn.commit()
        eph(respond, f":white_check_mark: You updated car `{car_id}` to {new_seats} seats.")
        post_announce(trip, channel_id, f":gear: <@{user}> updated car `{car_id}` to {new_seats} seats on *{trip}*.")

    @bolt_app.command("/delete")
    def cmd_delete(ack, respond, command):
        ack()
        car_id_str = (command.get("text") or "").strip()
        if not car_id_str:
            return eph(respond, "Usage: `/delete CarID`")
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
        if row[0] != user:
            return eph(respond, ":x: Only the car creator can delete it.")
        creator, name, trip = row
        
        # Get all members to notify them
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM car_members WHERE car_id=%s", (car_id,))
            members = [row[0] for row in cur.fetchall()]
            cur.execute("DELETE FROM cars WHERE id=%s", (car_id,))
            conn.commit()
        
        # Notify all members
        for member in members:
            bolt_app.client.chat_postMessage(channel=member, text=f":wastebasket: Car `{car_id}` (*{name}*) on *{trip}* was deleted by its creator.")
        eph(respond, f":white_check_mark: You deleted car `{car_id}` (*{name}*).")
        post_announce(trip, channel_id, f":wastebasket: <@{user}> deleted car `{car_id}` (*{name}*) on *{trip}*.")
