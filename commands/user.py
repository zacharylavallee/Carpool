"""
User-focused commands for the carpool bot
"""
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, get_active_trip, get_channel_members

def register_user_commands(bolt_app):
    """Register user-focused commands"""
    
    @bolt_app.command("/mycars")
    def cmd_mycars(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        user = command["user_id"]
        
        # Get the active trip for this channel
        trip_info = get_active_trip(channel_id)
        if not trip_info:
            return eph(respond, ":x: No active trip in this channel. Create one with `/createtrip TripName` first.")
        trip = trip_info[0]
        
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            # Cars I created
            cur.execute(
                """
                SELECT c.id, c.name, c.seats
                FROM cars c
                WHERE c.trip=%s AND c.created_by=%s
                ORDER BY c.id
                """, (trip, user)
            )
            created = cur.fetchall()
            # Cars I joined (but didn't create)
            cur.execute(
                """
                SELECT c.id, c.name, c.seats
                FROM cars c
                JOIN car_members m ON m.car_id = c.id
                WHERE c.trip=%s AND m.user_id=%s AND c.created_by != %s
                ORDER BY c.id
                """, (trip, user, user)
            )
            joined = cur.fetchall()
        if not created and not joined:
            return eph(respond, f"You have no cars on *{trip}*.")
        lines = []
        if created:
            lines.append("*Cars you created:*")
            for c in created:
                lines.append(f"• `{c['id']}`: *{c['name']}* ({c['seats']} seats)")
        if joined:
            if lines:
                lines.append("")
            lines.append("*Cars you joined:*")
            for c in joined:
                lines.append(f"• `{c['id']}`: *{c['name']}* ({c['seats']} seats)")
        eph(respond, "\n".join(lines))

    @bolt_app.command("/mytrips")
    def cmd_mytrips(ack, respond, command):
        ack()
        user = command["user_id"]
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT t.name
                FROM trips t
                LEFT JOIN cars c ON c.trip = t.name AND c.channel_id = t.channel_id
                LEFT JOIN car_members m ON m.car_id = c.id
                WHERE t.created_by = %s OR c.created_by = %s OR m.user_id = %s
                ORDER BY t.name
                """, (user, user, user)
            )
            trips = [row[0] for row in cur.fetchall()]
        if not trips:
            return eph(respond, "You haven't joined or created any trips yet.")
        lines = [f"• *{trip}*" for trip in trips]
        eph(respond, f"Your trips:\n" + "\n".join(lines))

    @bolt_app.command("/needride")
    def cmd_needride(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Get the active trip for this channel
        trip_info = get_active_trip(channel_id)
        if not trip_info:
            return eph(respond, ":x: No active trip in this channel. Create one with `/createtrip TripName` first.")
        trip = trip_info[0]
        
        # Get all members of this channel
        channel_members = get_channel_members(channel_id)
        if not channel_members:
            return eph(respond, ":x: Could not retrieve channel members.")
        
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Get channel members who are NOT in any car for this trip
            cur.execute(
                """
                SELECT DISTINCT m.user_id
                FROM car_members m
                JOIN cars c ON c.id = m.car_id
                WHERE c.trip = %s AND c.channel_id = %s
                """, (trip, channel_id)
            )
            members_with_rides = {row['user_id'] for row in cur.fetchall()}
        
        # Find channel members who need rides
        members_needing_rides = [user_id for user_id in channel_members if user_id not in members_with_rides]
        
        if not members_needing_rides:
            return eph(respond, f"All channel members already have rides for *{trip}*!")
        
        # Show available cars with space
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                """
                SELECT c.id, c.name, c.seats, c.created_by, COUNT(m.user_id) as filled
                FROM cars c
                LEFT JOIN car_members m ON m.car_id = c.id
                WHERE c.trip = %s AND c.channel_id = %s
                GROUP BY c.id, c.name, c.seats, c.created_by
                HAVING COUNT(m.user_id) < c.seats
                ORDER BY c.id
                """, (trip, channel_id)
            )
            available_cars = cur.fetchall()
        
        response_lines = []
        
        # Show members who need rides
        member_mentions = [f"<@{user_id}>" for user_id in members_needing_rides]
        response_lines.append(f"**Channel members who need rides for *{trip}*:**")
        response_lines.append(", ".join(member_mentions))
        response_lines.append("")
        
        # Show available cars
        if available_cars:
            response_lines.append("**Available cars with space:**")
            for car in available_cars:
                available_seats = car['seats'] - car['filled']
                response_lines.append(f"• `{car['id']}`: *{car['name']}* - {available_seats} seats available (created by <@{car['created_by']}>)")
            response_lines.append("")
            response_lines.append("Use `/requestjoin CarID` to join a car!")
        else:
            response_lines.append("**No cars with available space.** Someone should create a new car with `/createcar`!")
        
        eph(respond, "\n".join(response_lines))
