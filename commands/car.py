"""
Car management commands for the carpool bot
"""
import psycopg2
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, get_active_trip, post_announce, get_username, get_next_available_car_id
from utils.channel_guard import check_bot_channel_access

def register_car_commands(bolt_app):
    """Register car management commands"""
    
    @bolt_app.command("/car")
    def cmd_car(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        seats_str = (command.get("text") or "").strip()
        if not seats_str:
            return eph(respond, "Usage: `/car seats` (e.g., `/car 4`)") 
        try:
            seats = int(seats_str)
        except ValueError:
            return eph(respond, ":x: seats must be a number.")
        user = command["user_id"]
        
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
        eph(respond, f":white_check_mark: You created *{name}* (ID `{car_id}`) with *{seats}* seats.")
        post_announce(trip, channel_id, f":car: <@{user}> created *{name}* (ID `{car_id}`) on *{trip}*.")

    @bolt_app.command("/list")
    def cmd_list(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
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

    @bolt_app.command("/info")
    def cmd_info(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Get ALL trips across ALL channels
            cur.execute(
                "SELECT name, created_by, created_at, channel_id FROM trips ORDER BY created_at DESC"
            )
            all_trips = cur.fetchall()
            
            if not all_trips:
                return eph(respond, ":x: No trips created yet. Create one with `/trip TripName` first.")
            
            # Get the active trip for THIS channel (if any)
            cur.execute(
                "SELECT name FROM trips WHERE channel_id=%s AND active=TRUE ORDER BY created_at DESC LIMIT 1",
                (channel_id,)
            )
            active_trip_row = cur.fetchone()
            active_trip = active_trip_row['name'] if active_trip_row else None
            
            # Build response starting with trip list
            response_parts = []
            
            # Show all trips across all channels
            response_parts.append(":round_pushpin: **All Trips Across All Channels:**")
            
            for trip in all_trips:
                # Check if this trip is active in this channel
                is_active_here = (trip['channel_id'] == channel_id and trip['name'] == active_trip)
                status = " (active in this channel)" if is_active_here else ""
                
                response_parts.append(f"• *{trip['name']}* by <@{trip['created_by']}> in <#{trip['channel_id']}>{status}")
            
            response_parts.append("")
            
            # Show car details for active trip in THIS channel (if any)
            if active_trip:
                response_parts.append(f":car: **Car Details for Active Trip in This Channel:** *{active_trip}*")
            else:
                response_parts.append(":information_source: **No active trip in this channel yet.** Use `/trip TripName` to create one.")
                eph(respond, "\n".join(response_parts))
                return
            
            # Get cars for the active trip
            cur.execute(
                """
                SELECT c.id, c.name, c.seats, ARRAY_AGG(m.user_id) AS members
                FROM cars c
                LEFT JOIN car_members m ON m.car_id=c.id
                WHERE c.trip=%s AND c.channel_id=%s
                GROUP BY c.id, c.name, c.seats
                ORDER BY c.id
                """, (active_trip, channel_id)
            )
            cars = cur.fetchall()
            
            if not cars:
                response_parts.append(f"No cars on *{active_trip}* yet.")
            else:
                for c in cars:
                    members = [m for m in c['members'] if m is not None]
                    if members:
                        member_mentions = " ".join([f"<@{m}>" for m in members])
                        response_parts.append(f"• `{c['id']}`: *{c['name']}* ({len(members)}/{c['seats']}) — {member_mentions}")
                    else:
                        response_parts.append(f"• `{c['id']}`: *{c['name']}* (0/{c['seats']}) — empty")
        
        eph(respond, "\n".join(response_parts))
