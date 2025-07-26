"""
Help command for the carpool bot
"""
from utils.helpers import eph

def register_help_commands(bolt_app):
    """Register help-related commands"""
    
    @bolt_app.command("/help")
    def cmd_help(ack, respond):
        ack()
        eph(respond, (
            "*Available commands:*\n"
            "`/help` – show this help message\n"
            "`/trip TripName` – create/replace the trip for this channel\n"
            "`/car seats` – create & join car (auto-named)\n"
            "`/list` – list cars on the active trip\n"
            "`/status` – show fill & members\n"
            "`/join CarID` – ask to join a car\n"
            "`/leave CarID` – leave a car you joined\n"
            "`/update CarID seats=X` – update seat count\n"
            "`/kick CarID @user` – remove a member (creator only)\n"
            "`/delete CarID` – delete a car (creator only)\n"
            "`/needride` – users not in any car\n"
        ))
