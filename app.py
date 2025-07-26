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

# Import command modules
from commands.help import register_help_commands
from commands.trip import register_trip_commands
from commands.car import register_car_commands
from commands.member import register_member_commands
from commands.manage import register_manage_commands
from commands.user import register_user_commands
from commands.settings import register_settings_commands

# ─── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Initialize database ─────────────────────────────────────────────────
init_db()

# ─── Slack Bolt App ──────────────────────────────────────────────────────
bolt_app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET")
)

# ─── Register all command modules ────────────────────────────────────────
register_help_commands(bolt_app)
register_trip_commands(bolt_app)
register_car_commands(bolt_app)
register_member_commands(bolt_app)
register_manage_commands(bolt_app)
register_user_commands(bolt_app)
register_settings_commands(bolt_app)

# ─── Flask app for WSGI ──────────────────────────────────────────────────
flask_app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)

# ─── WSGI entrypoint ─────────────────────────────────────────────────────
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

# ─── Health‑check endpoint ───────────────────────────────────────────────
@flask_app.route("/")
def index():
    return jsonify({"status": "Carpool Bot is running!"})

if __name__ == "__main__":
    flask_app.run(port=3000)
