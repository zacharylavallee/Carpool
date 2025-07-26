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
            "`/car seats` – create & join car (auto-named)\n"
            "`/list` – list cars on the active trip\n"
            "`/info` – show car details & members\n"
            "`/in CarID` – request to join a car\n"
            "`/out CarID` – leave a car you joined\n"
            "`/update CarID seats=X` – update seat count\n"
            "`/boot CarID @user` – remove a member (creator only)\n"
            "`/delete CarID` – delete a car (creator only)\n"
            "`/needride` – users not in any car\n"
        ))
