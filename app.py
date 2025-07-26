# app.py
import os
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime

from dotenv import load_dotenv, find_dotenv
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

# ─── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Load env & connect to Postgres ─────────────────────────────────────
# Load environment variables via .env file (if present)
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
    logger.info(f"Loaded .env from {dotenv_path}")
else:
    logger.warning(".env file not found; relying on environment variables")
# Retrieve database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL is not set. Exiting.")
    exit(1)
logger.info(f"DATABASE_URL={DATABASE_URL}")


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ─── Initialize DB schema ────────────────────────────────────────────────
def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        # Trips
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            name TEXT PRIMARY KEY,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        # Cars
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id SERIAL PRIMARY KEY,
            trip TEXT NOT NULL REFERENCES trips(name) ON DELETE CASCADE,
            name TEXT NOT NULL,
            seats INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trip, created_by)
        )""")
        # Memberships
        cur.execute("""
        CREATE TABLE IF NOT EXISTS car_members (
            car_id INTEGER REFERENCES cars(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(car_id, user_id)
        )""")
        # Join requests
        cur.execute("""
        CREATE TABLE IF NOT EXISTS join_requests (
            car_id INTEGER REFERENCES cars(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(car_id, user_id)
        )""")
        # Trip settings
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trip_settings (
            trip TEXT PRIMARY KEY REFERENCES trips(name) ON DELETE CASCADE,
            channel_id TEXT NOT NULL
        )""")
        conn.commit()

init_db()

# ─── Slack Bolt App ──────────────────────────────────────────────────────
bolt_app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET")
)
flask_app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)

def eph(respond, text):
    respond(text=text, response_type="ephemeral")

def post_announce(trip: str, text: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT channel_id FROM trip_settings WHERE trip=%s", (trip,))
        row = cur.fetchone()
        if row:
            bolt_app.client.chat_postMessage(channel=row[0], text=text)

# ─── /help ────────────────────────────────────────────────────────────────
@bolt_app.command("/help")
def cmd_help(ack, respond):
    ack()
    eph(respond, (
        "*Available commands:*\n"
        "`/createtrip TripName` – define a new trip\n"
        "`/deletetrip TripName` – delete a trip\n"
        "`/settripchannel TripName #channel` – announcements\n"
        "`/createcar TripName CarName seats` – create & join car\n"
        "`/listcars TripName` – list cars on a trip\n"
        "`/carstatus TripName` – show fill & members\n"
        "`/requestjoin CarID` – ask to join a car\n"
        "`/leavecar CarID` – leave a car you joined\n"
        "`/renamecar CarID NewName` – rename your car\n"
        "`/updatecar CarID seats=X` – update seat count\n"
        "`/removeuser CarID @user` – remove a member (creator only)\n"
        "`/removecar CarID` – delete a car (creator only)\n"
        "`/mycars TripName` – your cars & joined cars\n"
        "`/mytrips` – trips you’ve joined or created\n"
        "`/needride TripName` – users not in any car\n"
    ))

# ─── /createtrip & /deletetrip ──────────────────────────────────────────
@bolt_app.command("/createtrip")
def cmd_createtrip(ack, respond, command):
    ack()
    trip = (command.get("text") or "").strip()
    if not trip:
        return eph(respond, "Usage: `/createtrip TripName`")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO trips(name, created_by) VALUES(%s,%s)",
                (trip, user)
            )
            conn.commit()
            eph(respond, f":round_pushpin: Trip *{trip}* created.")
        except psycopg2.errors.UniqueViolation:
            eph(respond, f":x: Trip *{trip}* already exists.")

@bolt_app.command("/deletetrip")
def cmd_deletetrip(ack, respond, command):
    ack()
    trip = (command.get("text") or "").strip()
    if not trip:
        return eph(respond, "Usage: `/deletetrip TripName`")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_by FROM trips WHERE name=%s", (trip,))
        row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Trip *{trip}* does not exist.")
        if row[0] != user:
            return eph(respond, ":x: Only the creator can delete this trip.")
        cur.execute("DELETE FROM trips WHERE name=%s", (trip,))
        conn.commit()
    eph(respond, f":wastebasket: Trip *{trip}* deleted.")

# ─── /settripchannel ───────────────────────────────────────────────────
@bolt_app.command("/settripchannel")
def cmd_settripchannel(ack, respond, command):
    ack()
    parts = (command.get("text") or "").split()
    if len(parts) != 2:
        return eph(respond, "Usage: `/settripchannel TripName #channel`")
    trip, channel = parts
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO trip_settings(trip, channel_id)
            VALUES(%s,%s)
            ON CONFLICT(trip) DO UPDATE SET channel_id=excluded.channel_id
            """, (trip, channel)
        )
        conn.commit()
    eph(respond, f":loudspeaker: Announcements for *{trip}* will post in {channel}.")

# ─── /createcar ────────────────────────────────────────────────────────
@bolt_app.command("/createcar")
def cmd_createcar(ack, respond, command):
    ack()
    parts = (command.get("text") or "").split()
    if len(parts) < 3:
        return eph(respond, "Usage: `/createcar TripName CarName seats`")
    trip, *name_parts, seats_str = parts
    name = " ".join(name_parts)
    try:
        seats = int(seats_str)
    except ValueError:
        return eph(respond, ":x: seats must be a number.")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM trips WHERE name=%s", (trip,))
        if not cur.fetchone():
            return eph(respond, f":x: Trip *{trip}* does not exist.")
        try:
            cur.execute(
                "INSERT INTO cars(trip, name, seats, created_by) VALUES(%s,%s,%s,%s) RETURNING id",
                (trip, name, seats, user)
            )
            car_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO car_members(car_id, user_id) VALUES(%s,%s)",
                (car_id, user)
            )
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            return eph(respond, ":x: You already created a car on this trip.")
    eph(respond, f":car: Created *{name}* (ID `{car_id}`) with *{seats}* seats.")
    post_announce(trip, f":car: <@{user}> created *{name}* (ID `{car_id}`) on *{trip}*.")

# ─── /listcars ──────────────────────────────────────────────────────────
@bolt_app.command("/listcars")
def cmd_listcars(ack, respond, command):
    ack()
    trip = (command.get("text") or "").strip()
    if not trip:
        return eph(respond, "Usage: `/listcars TripName`")
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(
            """
            SELECT c.id, c.name, c.seats, COUNT(m.user_id) AS joined
            FROM cars c
            LEFT JOIN car_members m ON m.car_id=c.id
            WHERE c.trip=%s
            GROUP BY c.id, c.name, c.seats
            ORDER BY c.id
            """, (trip,)
        )
        cars = cur.fetchall()
    if not cars:
        return eph(respond, f"No cars on *{trip}* yet.")
    lines = [
        f"• `{c['id']}`: *{c['name']}* ({c['seats']} seats) — {c['joined']} joined"
        for c in cars
    ]
    eph(respond, f"Cars on *{trip}*:\n" + "\n".join(lines))

# ─── /carstatus ────────────────────────────────────────────────────────
@bolt_app.command("/carstatus")
def cmd_carstatus(ack, respond, command):
    ack()
    trip = (command.get("text") or "").strip()
    if not trip:
        return eph(respond, "Usage: `/carstatus TripName`")
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(
            """
            SELECT c.id, c.name, c.seats, ARRAY_AGG(m.user_id) AS members
            FROM cars c
            LEFT JOIN car_members m ON m.car_id=c.id
            WHERE c.trip=%s
            GROUP BY c.id, c.name, c.seats
            ORDER BY c.id
            """, (trip,)
        )
        cars = cur.fetchall()
    if not cars:
        return eph(respond, f"No cars on *{trip}* yet.")
    lines = []
    for c in cars:
        memb = [f"<@{u}>" for u in c['members'] if u]
        count = len(memb)
        left = c['seats'] - count
        lines.append(f"*{c['name']}* (`{c['id']}`): {count}/{c['seats']} filled, {left} open — Members: {', '.join(memb) or '_none_'}")
    eph(respond, f"*Status for {trip}*:\n" + "\n".join(lines))

# ─── /requestjoin & interactive handlers ───────────────────────────────
@bolt_app.command("/requestjoin")
def cmd_requestjoin(ack, respond, command):
    ack()
    try:
        car_id = int((command.get("text") or "").strip())
    except ValueError:
        return eph(respond, "Usage: `/requestjoin CarID`")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT trip, name, seats, created_by FROM cars WHERE id=%s", (car_id,))
        row = cur.fetchone()
    if not row:
        return eph(respond, f":x: Car `{car_id}` does not exist.")
    trip, name, seats, creator = row
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM car_members m
            JOIN cars c ON c.id=m.car_id
            WHERE c.trip=%s AND m.user_id=%s
            """, (trip, user)
        )
        if cur.fetchone():
            return eph(respond, ":x: You’ve already joined a car on this trip.")
        cur.execute(
            "INSERT INTO join_requests(car_id, user_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (car_id, user)
        )
        conn.commit()
    bolt_app.client.chat_postMessage(
        channel=creator,
        blocks=[
            {"type":"section","text":{"type":"mrkdwn","text":f"<@{user}> wants to join *{name}* (`{car_id}`) on *{trip}*."}},
            {"type":"actions","elements":[
                {"type":"button","text":{"type":"plain_text","text":"Approve"},"style":"primary","action_id":"approve_request","value":f"{car_id}|{user}"},
                {"type":"button","text":{"type":"plain_text","text":"Deny"},"style":"danger","action_id":"deny_request","value":f"{car_id}|{user}"}
            ]},
        ],
        text="Join request"
    )
    eph(respond, f"Requested to join car `{car_id}`—<@{creator}> will approve.")

@bolt_app.action("approve_request")
def act_approve(ack, body, client):
    ack()
    car_id, user_to_add = body["actions"][0]["value"].split("|")
    approver = body["user"]["id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT seats, trip, created_by FROM cars WHERE id=%s", (car_id,))
        row = cur.fetchone()
    if not row or row[2] != approver:
        client.chat_postEphemeral(channel=approver, user=approver, text=":x: You can’t approve that.")
        return
    seats, trip, _ = row
    members = []
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM car_members WHERE car_id=%s", (car_id,))
        members = [r[0] for r in cur.fetchall()]
    if len(members) >= seats:
        client.chat_postEphemeral(channel=approver, user=approver, text=":x: Car is full.")
        return
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO car_members(car_id,user_id) VALUES(%s,%s)", (car_id, user_to_add))
        cur.execute("DELETE FROM join_requests WHERE car_id=%s AND user_id=%s", (car_id, user_to_add))
        conn.commit()
    client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":white_check_mark: Approved <@{user_to_add}> for car `{car_id}`.", blocks=[])
    client.chat_postMessage(channel=user_to_add, text=f":white_check_mark: You were approved for car `{car_id}`.")
    post_announce(trip, f":seat: <@{user_to_add}> joined car `{car_id}` on *{trip}*.")

@bolt_app.action("deny_request")
def act_deny(ack, body, client):
    ack()
    car_id, user_to_deny = body["actions"][0]["value"].split("|")
    denier = body["user"]["id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_by, trip FROM cars WHERE id=%s", (car_id,))
        row = cur.fetchone()
    if not row or row[0] != denier:
        client.chat_postEphemeral(channel=denier, user=denier, text=":x: You can’t deny that.")
        return
    trip = row[1]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM join_requests WHERE car_id=%s AND user_id=%s", (car_id, user_to_deny))
        conn.commit()
    client.chat_update(channel=body["channel"]["id"], ts=body["container"]["message_ts"], text=f":x: Denied <@{user_to_deny}> for car `{car_id}`.", blocks=[])
    client.chat_postMessage(channel=user_to_deny, text=f":x: Your request for car `{car_id}` was denied.")

@bolt_app.command("/leavecar")
def cmd_leavecar(ack, respond, command):
    ack()
    try:
        car_id = int((command.get("text") or "").strip())
    except ValueError:
        return eph(respond, "Usage: `/leavecar CarID`")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT trip FROM cars WHERE id=%s", (car_id,))
        row = cur.fetchone()
    if not row:
        return eph(respond, f":x: Car `{car_id}` does not exist.")
    trip = row[0]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM car_members WHERE car_id=%s AND user_id=%s", (car_id, user))
        conn.commit()
    eph(respond, f":wave: You left car `{car_id}`.")
    post_announce(trip, f":dash: <@{user}> left car `{car_id}` on *{trip}*.")

# ─── WSGI entrypoint ─────────────────────────────────────────────────────
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

# ─── Health‑check endpoint ───────────────────────────────────────────────
@flask_app.route("/", methods=["GET"])
def index():
    return "✅ Carpool bot is running!", 200

if __name__ == "__main__":
    flask_app.run(port=3000)

