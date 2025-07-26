"""
User-focused commands for the carpool bot
"""
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, get_active_trip, get_channel_members

def register_user_commands(bolt_app):
    """Register user-focused commands"""
    




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
