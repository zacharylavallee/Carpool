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
            "`/createtrip TripName` – create/replace the trip for this channel\n"
            "`/createcar seats` – create & join car (auto-named)\n"
            "`/listcars` – list cars on the active trip\n"
            "`/carstatus` – show fill & members\n"
            "`/requestjoin CarID` – ask to join a car\n"
            "`/leavecar CarID` – leave a car you joined\n"
            "`/updatecar CarID seats=X` – update seat count\n"
            "`/removeuser CarID @user` – remove a member (creator only)\n"
            "`/removecar CarID` – delete a car (creator only)\n"
            "`/needride` – users not in any car\n"
        ))
