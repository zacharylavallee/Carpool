# app.py
import os
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime

from dotenv import load_dotenv, find_dotenv
from flask import Flask, request, jsonify
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
            name TEXT,
            channel_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(name, channel_id)
        )""")
        # Cars
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id SERIAL PRIMARY KEY,
            trip TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            name TEXT NOT NULL,
            seats INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(trip, channel_id) REFERENCES trips(name, channel_id) ON DELETE CASCADE,
            UNIQUE(trip, channel_id, created_by)
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
            trip TEXT,
            channel_id TEXT,
            announcement_channel_id TEXT NOT NULL,
            PRIMARY KEY(trip, channel_id),
            FOREIGN KEY(trip, channel_id) REFERENCES trips(name, channel_id) ON DELETE CASCADE
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

def get_channel_members(channel_id):
    """Get list of user IDs who are members of the given channel."""
    try:
        result = bolt_app.client.conversations_members(channel=channel_id)
        return result["members"]
    except Exception as e:
        logger.error(f"Error getting channel members: {e}")
        return []

def post_announce(trip: str, channel_id: str, text: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT announcement_channel_id FROM trip_settings WHERE trip=%s AND channel_id=%s", (trip, channel_id))
        row = cur.fetchone()
        if row:
            bolt_app.client.chat_postMessage(channel=row[0], text=text)

# ─── /help ────────────────────────────────────────────────────────────────
@bolt_app.command("/help")
def cmd_help(ack, respond):
    ack()
    eph(respond, (
        "*Available commands:*\n"
        "`/help` – show this help message\n"
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
    channel_id = command["channel_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO trips(name, channel_id, created_by) VALUES(%s,%s,%s)",
                (trip, channel_id, user)
            )
            conn.commit()
            eph(respond, f":round_pushpin: Trip *{trip}* created for this channel.")
        except psycopg2.errors.UniqueViolation:
            eph(respond, f":x: Trip *{trip}* already exists in this channel.")

@bolt_app.command("/deletetrip")
def cmd_deletetrip(ack, respond, command):
    ack()
    trip = (command.get("text") or "").strip()
    if not trip:
        return eph(respond, "Usage: `/deletetrip TripName`")
    user = command["user_id"]
    channel_id = command["channel_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_by FROM trips WHERE name=%s AND channel_id=%s", (trip, channel_id))
        row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Trip *{trip}* does not exist in this channel.")
        if row[0] != user:
            return eph(respond, ":x: Only the creator can delete this trip.")
        cur.execute("DELETE FROM trips WHERE name=%s AND channel_id=%s", (trip, channel_id))
        conn.commit()
    eph(respond, f":wastebasket: Trip *{trip}* deleted from this channel.")

# ─── /settripchannel ───────────────────────────────────────────────────
@bolt_app.command("/settripchannel")
def cmd_settripchannel(ack, respond, command):
    ack()
    parts = (command.get("text") or "").split()
    if len(parts) != 2:
        return eph(respond, "Usage: `/settripchannel TripName #channel`")
    trip, announcement_channel = parts
    user = command["user_id"]
    channel_id = command["channel_id"]
    # Check if trip exists in this channel
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_by FROM trips WHERE name=%s AND channel_id=%s", (trip, channel_id))
        row = cur.fetchone()
        if not row:
            return eph(respond, f":x: Trip *{trip}* does not exist in this channel.")
        if row[0] != user:
            return eph(respond, ":x: Only the trip creator can set the announcement channel.")
        cur.execute(
            """
            INSERT INTO trip_settings(trip, channel_id, announcement_channel_id)
            VALUES(%s,%s,%s)
            ON CONFLICT(trip, channel_id) DO UPDATE SET announcement_channel_id=excluded.announcement_channel_id
            """, (trip, channel_id, announcement_channel)
        )
        conn.commit()
    eph(respond, f":loudspeaker: Announcements for *{trip}* will post in {announcement_channel}.")

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
    channel_id = command["channel_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM trips WHERE name=%s AND channel_id=%s", (trip, channel_id))
        if not cur.fetchone():
            return eph(respond, f":x: Trip *{trip}* does not exist in this channel.")
        try:
            cur.execute(
                "INSERT INTO cars(trip, channel_id, name, seats, created_by) VALUES(%s,%s,%s,%s,%s) RETURNING id",
                (trip, channel_id, name, seats, user)
            )
            car_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO car_members(car_id, user_id) VALUES(%s,%s)",
                (car_id, user)
            )
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            return eph(respond, ":x: You already created a car on this trip in this channel.")
    eph(respond, f":car: Created *{name}* (ID `{car_id}`) with *{seats}* seats.")
    post_announce(trip, channel_id, f":car: <@{user}> created *{name}* (ID `{car_id}`) on *{trip}*.")

# ─── /listcars ──────────────────────────────────────────────────────────
@bolt_app.command("/listcars")
def cmd_listcars(ack, respond, command):
    ack()
    trip = (command.get("text") or "").strip()
    if not trip:
        return eph(respond, "Usage: `/listcars TripName`")
    channel_id = command["channel_id"]
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(
            """
            SELECT c.id, c.name, c.seats, COUNT(m.user_id) AS joined
            FROM cars c
            LEFT JOIN car_members m ON m.car_id=c.id
            WHERE c.trip=%s AND c.channel_id=%s
            GROUP BY c.id, c.name, c.seats
            ORDER BY c.id
            """, (trip, channel_id)
        )
        cars = cur.fetchall()
    if not cars:
        return eph(respond, f"No cars on *{trip}* in this channel yet.")
    lines = [
        f"• `{c['id']}`: *{c['name']}* ({c['seats']} seats) — {c['joined']} joined"
        for c in cars
    ]
    eph(respond, f"Cars on *{trip}* in this channel:\n" + "\n".join(lines))

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

# ─── /renamecar ─────────────────────────────────────────────────────────
@bolt_app.command("/renamecar")
def cmd_renamecar(ack, respond, command):
    ack()
    parts = (command.get("text") or "").split()
    if len(parts) < 2:
        return eph(respond, "Usage: `/renamecar CarID NewName`")
    try:
        car_id = int(parts[0])
    except ValueError:
        return eph(respond, ":x: CarID must be a number.")
    new_name = " ".join(parts[1:])
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_by, trip FROM cars WHERE id=%s", (car_id,))
        row = cur.fetchone()
    if not row:
        return eph(respond, f":x: Car `{car_id}` does not exist.")
    if row[0] != user:
        return eph(respond, ":x: Only the creator can rename this car.")
    trip = row[1]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE cars SET name=%s WHERE id=%s", (new_name, car_id))
        conn.commit()
    eph(respond, f":pencil2: Renamed car `{car_id}` to *{new_name}*.")
    post_announce(trip, f":pencil2: <@{user}> renamed car `{car_id}` to *{new_name}* on *{trip}*.")

# ─── /updatecar ─────────────────────────────────────────────────────────
@bolt_app.command("/updatecar")
def cmd_updatecar(ack, respond, command):
    ack()
    parts = (command.get("text") or "").split()
    if len(parts) != 2 or not parts[1].startswith("seats="):
        return eph(respond, "Usage: `/updatecar CarID seats=X`")
    try:
        car_id = int(parts[0])
        new_seats = int(parts[1].split("=")[1])
    except (ValueError, IndexError):
        return eph(respond, ":x: Invalid format. Use `/updatecar CarID seats=X`")
    if new_seats < 1:
        return eph(respond, ":x: Seats must be at least 1.")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_by, trip FROM cars WHERE id=%s", (car_id,))
        row = cur.fetchone()
    if not row:
        return eph(respond, f":x: Car `{car_id}` does not exist.")
    if row[0] != user:
        return eph(respond, ":x: Only the creator can update this car.")
    trip = row[1]
    # Check if new seat count would be less than current members
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM car_members WHERE car_id=%s", (car_id,))
        current_members = cur.fetchone()[0]
    if new_seats < current_members:
        return eph(respond, f":x: Cannot reduce seats to {new_seats}. Car has {current_members} members.")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE cars SET seats=%s WHERE id=%s", (new_seats, car_id))
        conn.commit()
    eph(respond, f":gear: Updated car `{car_id}` to {new_seats} seats.")
    post_announce(trip, f":gear: <@{user}> updated car `{car_id}` to {new_seats} seats on *{trip}*.")

# ─── /removeuser ────────────────────────────────────────────────────────
@bolt_app.command("/removeuser")
def cmd_removeuser(ack, respond, command):
    ack()
    parts = (command.get("text") or "").split()
    if len(parts) != 2:
        return eph(respond, "Usage: `/removeuser CarID @user`")
    try:
        car_id = int(parts[0])
    except ValueError:
        return eph(respond, ":x: CarID must be a number.")
    target_user = parts[1].strip("<@>")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_by, trip FROM cars WHERE id=%s", (car_id,))
        row = cur.fetchone()
    if not row:
        return eph(respond, f":x: Car `{car_id}` does not exist.")
    if row[0] != user:
        return eph(respond, ":x: Only the creator can remove users from this car.")
    if row[0] == target_user:
        return eph(respond, ":x: You cannot remove yourself. Use `/removecar` to delete the car.")
    trip = row[1]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM car_members WHERE car_id=%s AND user_id=%s", (car_id, target_user))
        if cur.rowcount == 0:
            return eph(respond, f":x: <@{target_user}> is not in car `{car_id}`.")
        conn.commit()
    eph(respond, f":boot: Removed <@{target_user}> from car `{car_id}`.")
    bolt_app.client.chat_postMessage(channel=target_user, text=f":boot: You were removed from car `{car_id}` on *{trip}*.")
    post_announce(trip, f":boot: <@{user}> removed <@{target_user}> from car `{car_id}` on *{trip}*.")

# ─── /removecar ─────────────────────────────────────────────────────────
@bolt_app.command("/removecar")
def cmd_removecar(ack, respond, command):
    ack()
    try:
        car_id = int((command.get("text") or "").strip())
    except ValueError:
        return eph(respond, "Usage: `/removecar CarID`")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_by, trip, name FROM cars WHERE id=%s", (car_id,))
        row = cur.fetchone()
    if not row:
        return eph(respond, f":x: Car `{car_id}` does not exist.")
    if row[0] != user:
        return eph(respond, ":x: Only the creator can delete this car.")
    trip, name = row[1], row[2]
    # Get members to notify them
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM car_members WHERE car_id=%s AND user_id != %s", (car_id, user))
        members = [r[0] for r in cur.fetchall()]
        # Delete the car (cascades to members and join requests)
        cur.execute("DELETE FROM cars WHERE id=%s", (car_id,))
        conn.commit()
    # Notify members
    for member in members:
        bolt_app.client.chat_postMessage(channel=member, text=f":wastebasket: Car `{car_id}` (*{name}*) on *{trip}* was deleted by its creator.")
    eph(respond, f":wastebasket: Deleted car `{car_id}` (*{name}*).")
    post_announce(trip, f":wastebasket: <@{user}> deleted car `{car_id}` (*{name}*) on *{trip}*.")

# ─── /mycars ────────────────────────────────────────────────────────────
@bolt_app.command("/mycars")
def cmd_mycars(ack, respond, command):
    ack()
    trip = (command.get("text") or "").strip()
    if not trip:
        return eph(respond, "Usage: `/mycars TripName`")
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # Cars I created
        cur.execute(
            "SELECT id, name, seats FROM cars WHERE trip=%s AND created_by=%s ORDER BY id",
            (trip, user)
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
    eph(respond, f"Your cars on *{trip}*:\n" + "\n".join(lines))

# ─── /mytrips ───────────────────────────────────────────────────────────
@bolt_app.command("/mytrips")
def cmd_mytrips(ack, respond, command):
    ack()
    user = command["user_id"]
    with get_conn() as conn:
        cur = conn.cursor()
        # Trips where I created a trip or car, or joined a car
        cur.execute(
            """
            SELECT DISTINCT t.name
            FROM trips t
            LEFT JOIN cars c ON c.trip = t.name
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

# ─── /needride ──────────────────────────────────────────────────────────
@bolt_app.command("/needride")
def cmd_needride(ack, respond, command):
    ack()
    trip = (command.get("text") or "").strip()
    if not trip:
        return eph(respond, "Usage: `/needride TripName`")
    channel_id = command["channel_id"]
    
    # Get all members of this channel
    channel_members = get_channel_members(channel_id)
    if not channel_members:
        return eph(respond, ":x: Could not retrieve channel members.")
    
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Check if trip exists in this channel
        cur.execute("SELECT 1 FROM trips WHERE name=%s AND channel_id=%s", (trip, channel_id))
        if not cur.fetchone():
            return eph(respond, f":x: Trip *{trip}* does not exist in this channel.")
        
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

# ─── WSGI entrypoint ─────────────────────────────────────────────────────
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json(force=True, silent=True) or {}
    # handle Slack URL verification challenge
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data["challenge"]})

    # otherwise pass to Bolt
    return handler.handle(request)

# ─── Health‑check endpoint ───────────────────────────────────────────────
@flask_app.route("/", methods=["GET"])
def index():
    return "✅ Carpool bot is running!", 200

if __name__ == "__main__":
    flask_app.run(port=3000)

