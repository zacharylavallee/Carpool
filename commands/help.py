"""
Help command for the carpool bot
"""
from utils.helpers import eph
from utils.channel_guard import check_bot_channel_access

def register_help_commands(bolt_app):
    """Register help-related commands"""
    
    @bolt_app.command("/help")
    def cmd_help(ack, respond, command):
        ack()
        channel_id = command["channel_id"]
        
        # Check if bot is in channel first
        if not check_bot_channel_access(channel_id, respond):
            return
        eph(respond, (
            "*Available commands:*\n"
            "`/help` – show this help message\n"
            "`/trip TripName` – create/replace the trip for this channel\n"
            "`/deletetrip TripName` – delete a trip (creator only)\n"
            "`/car seats` – create & join car (auto-named)\n"
            "`/list` – list cars on the active trip\n"
            "`/info` – show all trips & car details\n"
            "`/in CarID` – request to join a car\n"
            "`/out` – leave your current car\n"
            "`/update seats` – update your car's seat count\n"
            "`/boot @user` – remove a member from your car\n"
            "`/delete` – delete your car\n"
            "`/needride` – users not in any car\n"
        ))
