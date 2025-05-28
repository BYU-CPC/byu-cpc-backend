from collections import defaultdict
from flask import Blueprint, request
import json
from auth import is_logged_in, get_user_id
from data.leaderboard import add_person_to_leaderboard, get_created_leaderboards, get_joined_leaderboards, get_leaderboard_details, get_accessible_leaderboards, upsert_leaderboard
from data.utils import get_db

leaderboard = Blueprint("leaderboard", __name__)

@leaderboard.route("/leaderboard")
def get_leaderboard_index():
    return json.dumps({})

@leaderboard.route("/leaderboard/upsert", methods=["POST"])
def create_leaderboard():
    if not is_logged_in():
        return "not signed in", 401
    data = request.json
    if data is None:
        return "bad request", 400
    data = defaultdict(lambda:None, data)
    user_id = get_user_id()
    name = data["name"]
    start = data["start"]
    finish = data["finish"]
    period = data["period"]
    public_view = data["public_view"]
    public_join = data["public_join"]
    scoring = data["scoring"]
    rules = data["rules"]
    id = data["id"]
    db, close = get_db()
    id = upsert_leaderboard(db, name, start, finish, period, public_view, public_join, scoring, rules, user_id, id)
    close()
    return json.dumps({'id': id})

@leaderboard.route("/leaderboard/join", methods=["POST"])
def join_leaderboard():
    data = request.json
    if data is None:
        return "bad request", 400
    if not is_logged_in():
        return "not signed in", 401
    user_id = get_user_id()
    invitation_id = data["invitation_id"]
    leaderboard_id = data["leaderboard_id"]
    db, close = get_db()
    added = add_person_to_leaderboard(db, user_id, invitation_id, leaderboard_id)
    close()
    if added: return "added"
    return "forbidden", 403

@leaderboard.route("/leaderboard/all_accessible")
def all_accessible_leaderboards():
    db,close = get_db()
    user_id = get_user_id()
    results = get_accessible_leaderboards(db, user_id)
    close()
    return json.dumps(results)

@leaderboard.route("/leaderboard/joined")
def all_joined_leaderboards():
    user_id = get_user_id()
    if not user_id: return "not signed in", 401
    db,close = get_db()
    results = get_joined_leaderboards(db, user_id)
    close()
    return json.dumps(results)


@leaderboard.route("/leaderboard/<leaderboard_id>")
def get_leaderboard(leaderboard_id):
    user_id = get_user_id(True)
    invitation_id = request.args.get('invitation_id')
    db, close = get_db()
    details = get_leaderboard_details(db, user_id if user_id else "x", leaderboard_id, invitation_id)
    close()
    return json.dumps(details)

@leaderboard.route("/leaderboard/created")
def my_leaderboards():
    user_id = get_user_id()
    if not user_id: return "not signed in", 401
    db,close = get_db()
    results = get_created_leaderboards(db, user_id)
    close()
    return json.dumps(results)
