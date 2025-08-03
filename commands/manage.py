"""
Car management commands for the carpool bot (update/remove cars)
"""
import psycopg2
import psycopg2.extras
from config.database import get_conn
from utils.helpers import eph, post_announce
from utils.channel_guard import check_bot_channel_access

def register_manage_commands(bolt_app):
    """Register car management commands"""
    
    @bolt_app.command("/update")
    def cmd_update(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        
        seats_str = (command.get("text") or "").strip()
        if not seats_str:
            return eph(respond, "Usage: `/update seats` (e.g., `/update 4`)") 
        
        try:
            new_seats = int(seats_str)
        except ValueError:
            return eph(respond, ":x: Seat count must be a number.")
        
        if new_seats < 1:
            return eph(respond, ":x: Seat count must be at least 1.")
        
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
                "SELECT id, name, seats FROM cars WHERE channel_id=%s AND trip=%s AND created_by=%s",
                (channel_id, trip, user)
            )
            car_row = cur.fetchone()
            
            if not car_row:
                return eph(respond, f":x: You don't have a car on *{trip}* to update.")
            
            car_id, car_name, current_seats = car_row
            
            # Check current member count
            cur.execute("SELECT COUNT(*) FROM car_members WHERE car_id=%s", (car_id,))
            current_members = cur.fetchone()[0]
            
            # Validate seat reduction
            if new_seats < current_members:
                return eph(respond, f":x: Cannot reduce seats to {new_seats}. Your car has {current_members} members. Remove some members first with `/boot @user`.")
        
        # Send confirmation prompt for seat update
        if new_seats == current_seats:
            return eph(respond, f":information_source: Your car (*{car_name}*) already has {new_seats} seats. No change needed.")
        
        change_text = f"from {current_seats} to {new_seats}"
        member_text = f" (with {current_members} members)" if current_members > 0 else " (empty)"
        
        respond({
            "text": f":gear: Update your car *{car_name}* seat count {change_text}?",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":gear: Update your car *{car_name}*{member_text} seat count {change_text}?"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Yes, Update"},
                            "style": "primary",
                            "action_id": "confirm_update_car",
                            "value": f"{car_id}:{channel_id}:{trip}:{new_seats}:{current_seats}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "action_id": "cancel_update_car",
                            "value": f"{car_id}"
                        }
                    ]
                }
            ]
        })

    @bolt_app.command("/delete")
    def cmd_delete(ack, respond, command):
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
            
            # Find the user's car in this trip
            cur.execute(
                "SELECT id, name FROM cars WHERE channel_id=%s AND trip=%s AND created_by=%s",
                (channel_id, trip, user)
            )
            car_row = cur.fetchone()
            
            if not car_row:
                return eph(respond, f":x: You don't have a car on *{trip}* to delete.")
            
            car_id, car_name = car_row
            
            # Check how many members are in the car
            cur.execute("SELECT COUNT(*) FROM car_members WHERE car_id=%s", (car_id,))
            member_count = cur.fetchone()[0]
        
        # Send confirmation prompt
        member_text = f" (with {member_count} members)" if member_count > 0 else " (empty)"
        respond({
            "text": f":warning: Are you sure you want to delete your car *{car_name}*{member_text}?",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":warning: Are you sure you want to delete your car *{car_name}*{member_text}?"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Yes, Delete"},
                            "style": "danger",
                            "action_id": "confirm_delete_car",
                            "value": f"{car_id}:{channel_id}:{trip}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "action_id": "cancel_delete_car",
                            "value": f"{car_id}"
                        }
                    ]
                }
            ]
        })

    @bolt_app.action("confirm_delete_car")
    def handle_confirm_delete_car(ack, body, client, respond):
        ack()
        car_id, channel_id, trip = body["actions"][0]["value"].split(":")
        car_id = int(car_id)
        user = body["user"]["id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Verify the user still owns this car
            cur.execute("SELECT name, created_by FROM cars WHERE id=%s", (car_id,))
            car_row = cur.fetchone()
            
            if not car_row or car_row[1] != user:
                try:
                    client.chat_update(
                        channel=body["channel"]["id"], 
                        ts=body["container"]["message_ts"], 
                        text=":x: Car no longer exists or you don't own it.", 
                        blocks=[]
                    )
                except Exception:
                    respond(":x: Car no longer exists or you don't own it.")
                return
            
            car_name = car_row[0]
            
            # Delete the car (CASCADE will handle car_members)
            cur.execute("DELETE FROM cars WHERE id=%s", (car_id,))
            conn.commit()
        
        # Update the message to show completion with error handling
        try:
            client.chat_update(
                channel=body["channel"]["id"], 
                ts=body["container"]["message_ts"], 
                text=f":white_check_mark: Your car (*{car_name}*) has been deleted.", 
                blocks=[]
            )
        except Exception:
            respond(f":white_check_mark: Your car (*{car_name}*) has been deleted.")
        
        # Removed public announcement - keep channel focused on conversation

        # Notify all members
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM car_members WHERE car_id=%s", (car_id,))
            members = [row[0] for row in cur.fetchall()]
        
        for member in members:
            if member != user:  # Don't notify the car creator
                try:
                    client.chat_postMessage(
                        channel=member, 
                        text=f":wastebasket: Your car (*{car_name}*) on *{trip}* was deleted by its creator."
                    )
                except Exception:
                    respond(f":wastebasket: Your car (*{car_name}*) on *{trip}* was deleted by its creator.")

    @bolt_app.action("cancel_delete_car")
    def handle_cancel_delete_car(ack, body, client, respond):
        ack()
        try:
            client.chat_update(
                channel=body["channel"]["id"], 
                ts=body["container"]["message_ts"], 
                text=":information_source: Car deletion cancelled.", 
                blocks=[]
            )
        except Exception:
            respond(":information_source: Car deletion cancelled.")

    @bolt_app.action("confirm_update_car")
    def handle_confirm_update_car(ack, body, client, respond):
        ack()
        car_id, channel_id, trip, new_seats, current_seats = body["actions"][0]["value"].split(":")
        car_id, new_seats, current_seats = int(car_id), int(new_seats), int(current_seats)
        user = body["user"]["id"]
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Verify the user still owns this car
            cur.execute("SELECT name, created_by FROM cars WHERE id=%s", (car_id,))
            car_row = cur.fetchone()
            
            if not car_row or car_row[1] != user:
                try:
                    client.chat_update(
                        channel=body["channel"]["id"], 
                        ts=body["container"]["message_ts"], 
                        text=":x: Car no longer exists or you don't own it.", 
                        blocks=[]
                    )
                except Exception:
                    respond(":x: Car no longer exists or you don't own it.")
                return
            
            car_name = car_row[0]
            
            # Update the car's seat count
            cur.execute("UPDATE cars SET seats=%s WHERE id=%s", (new_seats, car_id))
            conn.commit()
        
        # Provide feedback based on whether seats increased or decreased
        if new_seats > current_seats:
            feedback = f":white_check_mark: Your car (*{car_name}*) now has {new_seats} seats (increased from {current_seats}). Extra spots are available for new members!"
        else:
            feedback = f":white_check_mark: Your car (*{car_name}*) now has {new_seats} seats (reduced from {current_seats}). All current members remain."
        
        # Update the message to show completion with error handling
        try:
            client.chat_update(
                channel=body["channel"]["id"], 
                ts=body["container"]["message_ts"], 
                text=feedback, 
                blocks=[]
            )
        except Exception:
            respond(feedback)
        
        # Removed public announcement - keep channel focused on conversation

    @bolt_app.action("cancel_update_car")
    def handle_cancel_update_car(ack, body, client, respond):
        ack()
        try:
            client.chat_update(
                channel=body["channel"]["id"], 
                ts=body["container"]["message_ts"], 
                text=":information_source: Car update cancelled.", 
                blocks=[]
            )
        except Exception:
            respond(":information_source: Car update cancelled.")
