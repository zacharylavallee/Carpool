"""
Car management commands for the carpool bot
"""
import psycopg2
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, get_active_trip, post_announce, get_username, get_next_available_car_id

def register_car_commands(bolt_app):
    """Register car management commands"""
    
    @bolt_app.command("/car")
    def cmd_car(ack, respond, command):
        ack()
        seats_str = (command.get("text") or "").strip()
        if not seats_str:
            return eph(respond, "Usage: `/car seats` (e.g., `/car 4`)") 
        try:
            seats = int(seats_str)
        except ValueError:
            return eph(respond, ":x: seats must be a number.")
        user = command["user_id"]
        channel_id = command["channel_id"]
        
        # Get the active trip for this channel
        trip_info = get_active_trip(channel_id)
        if not trip_info:
            return eph(respond, ":x: No active trip in this channel. Create one with `/trip TripName` first.")
        trip = trip_info[0]
        
        # Get username for car naming
        username = get_username(user)
        name = f"{username}'s car"
        
        # Get the next available car ID (reuses deleted IDs)
        car_id = get_next_available_car_id(trip, channel_id)
        
        with get_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO cars(id, trip, channel_id, name, seats, created_by) VALUES(%s,%s,%s,%s,%s,%s)",
                    (car_id, trip, channel_id, name, seats, user)
                )
                cur.execute(
                    "INSERT INTO car_members(car_id, user_id) VALUES(%s,%s)",
                    (car_id, user)
                )
                conn.commit()
            except psycopg2.errors.UniqueViolation:
                return eph(respond, ":x: You already created a car on this trip in this channel.")
        eph(respond, f":car: Created *{name}* (ID `{car_id}`) with *{seats}* seats.")
        post_announce(trip, channel_id, f":car: <@{user}> created *{name}* (ID `{car_id}`) on *{trip}*.")

    @bolt_app.command("/list")
    def cmd_list(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Get the active trip for this channel
        trip_info = get_active_trip(channel_id)
        if not trip_info:
            return eph(respond, ":x: No active trip in this channel. Create one with `/trip TripName` first.")
        trip = trip_info[0]
        
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                """
                SELECT c.id, c.name, c.seats, COUNT(m.user_id) AS joined
                FROM cars c
                LEFT JOIN car_members m ON m.car_id=c.id
                WHERE c.trip=%s AND c.channel_id=%s
                GROUP BY c.id, c.name, c.seats
                ORDER BY c.id
                """, (trip, channel_id)
            )
            cars = cur.fetchall()
        if not cars:
            return eph(respond, f"No cars on *{trip}* in this channel yet.")
        lines = [
            f"• `{c['id']}`: *{c['name']}* ({c['seats']} seats) — {c['joined']} joined"
            for c in cars
        ]
        eph(respond, f"Cars on *{trip}* in this channel:\n" + "\n".join(lines))

    @bolt_app.command("/status")
    def cmd_status(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Get the active trip for this channel
        trip_info = get_active_trip(channel_id)
        if not trip_info:
            return eph(respond, ":x: No active trip in this channel. Create one with `/trip TripName` first.")
        trip = trip_info[0]
        
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                """
                SELECT c.id, c.name, c.seats, ARRAY_AGG(m.user_id) AS members
                FROM cars c
                LEFT JOIN car_members m ON m.car_id=c.id
                WHERE c.trip=%s
                GROUP BY c.id, c.name, c.seats
                ORDER BY c.id
                """, (trip,)
            )
            cars = cur.fetchall()
        if not cars:
            return eph(respond, f"No cars on *{trip}* yet.")
        lines = []
        for c in cars:
            members = [m for m in c['members'] if m is not None]
            if members:
                member_mentions = " ".join([f"<@{m}>" for m in members])
                lines.append(f"• `{c['id']}`: *{c['name']}* ({len(members)}/{c['seats']}) — {member_mentions}")
            else:
                lines.append(f"• `{c['id']}`: *{c['name']}* (0/{c['seats']}) — empty")
        eph(respond, f"Car status for *{trip}*:\n" + "\n".join(lines))
