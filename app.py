"""
Carpool Bot - Main application entry point
Modular structure with commands organized in separate files
"""
import os
import logging
from flask import Flask, request, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

# Import configuration and utilities
from config.database import init_db
from utils.helpers import eph

# Import command modules - CLEAN STATE, NO HOME TAB
from commands.help import register_help_commands
from commands.trip import register_trip_commands
from commands.car import register_car_commands
from commands.member import register_member_commands
from commands.manage import register_manage_commands
from middleware.channel_restrictions import register_channel_restrictions
from commands.user import register_user_commands
# from commands.home_tab import register_home_tab_handlers  # DISABLED
from commands.channel_events import register_channel_event_handlers


# ─── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Initialize database ─────────────────────────────────────────────────
init_db()

# ─── Slack Bolt App ──────────────────────────────────────────────────────
from slack_bolt.oauth.oauth_settings import OAuthSettings

# OAuth settings for public distribution (if client ID/secret provided)
client_id = os.getenv("SLACK_CLIENT_ID")
client_secret = os.getenv("SLACK_CLIENT_SECRET")
bot_token = os.getenv("SLACK_BOT_TOKEN")

if client_id and client_secret:
    # Use OAuth for public distribution
    oauth_settings = OAuthSettings(
        client_id=client_id,
        client_secret=client_secret,
        scopes=["commands", "chat:write", "groups:read", "im:write", "users:read"]
    )
    bolt_app = App(
        signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
        oauth_settings=oauth_settings
    )
else:
    # Fallback to direct token (for development)
    bolt_app = App(
        token=bot_token,
        signing_secret=os.getenv("SLACK_SIGNING_SECRET")
    )

# ─── Register middleware ────────────────────────────────────────────────
register_channel_restrictions(bolt_app)

# ─── Register all command modules ────────────────────────────────────────
register_help_commands(bolt_app)
register_trip_commands(bolt_app)
register_car_commands(bolt_app)
register_member_commands(bolt_app)
register_manage_commands(bolt_app)
register_user_commands(bolt_app)
# register_home_tab_handlers(bolt_app)  # DISABLED
register_channel_event_handlers(bolt_app)


# ─── Flask app for WSGI ──────────────────────────────────────────────────
flask_app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)

# ─── WSGI entrypoint ─────────────────────────────────────────────────────
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    try:
        # Handle URL verification challenge (JSON content)
        if request.content_type == 'application/json' and request.json and request.json.get("type") == "url_verification":
            return request.json.get("challenge")
        
        # Handle normal Slack events and slash commands
        return handler.handle(request)
    except Exception as e:
        print(f"Error in slack_events: {e}")
        return {"error": "Internal server error"}, 500

# ─── OAuth endpoints for public distribution ─────────────────────────────
@flask_app.route("/slack/install", methods=["GET"])
def install():
    return handler.handle(request)

@flask_app.route("/slack/oauth_redirect", methods=["GET"])
def oauth_redirect():
    return handler.handle(request)

# ─── Health‑check endpoint ───────────────────────────────────────────────
@flask_app.route("/")
def index():
    return jsonify({"status": "Carpool Bot is running!"})

if __name__ == "__main__":
    flask_app.run(port=3000)

# Debug registered listeners
print("\n🔍 REGISTERED LISTENERS:")
print("======================")
for listener in bolt_app._listeners:
    print(f"- {listener}")
print("======================\n")
