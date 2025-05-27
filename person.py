from flask import Blueprint, request
from data.utils import get_db
from auth import is_logged_in, get_user_id
from data.person import get_user_profile, upsert_platform_login, add_person, get_all_users
import requests
import json

person = Blueprint("person", __name__)
@person.route("/set_username", methods=["POST"])
def set_username():
    data = request.json
    if data is None:
        return "bad request", 400
    if not is_logged_in():
        return "not signed in", 401
    user_id = get_user_id()
    username = data["username"]
    platform = data["platform"]
    db, close = get_db()
    upsert_platform_login(db, user_id, username, platform)
    close()
    return "ok"


@person.route("/validate_username", methods=["POST"])
def validate_username():
    data = request.json
    if data is None:
        return "bad_request", 400
    username = data["username"]
    platform = data["platform"]
    url = f"https://open.kattis.com/users/{username}" if platform == "kattis" else f"https://codeforces.com/api/user.info?handles={username}"
    response = requests.get(url)
    return {"valid": response.status_code == 200}


@person.route("/get_profile", methods=["POST"])
def get_profile():
    if not is_logged_in():
        return "not signed in", 401
    db, close = get_db()
    person_id = get_user_id()
    user_data = get_user_profile(db,person_id)
    close()
    return json.dumps(user_data), 200


@person.route("/create_user", methods=["POST"])
def create_user():
    if not is_logged_in(): return "not signed in", 401
    data = request.json
    if data is None:
        return "bad request", 400
    person_id = get_user_id()
    display_name = data["display_name"]
    codeforces_username = (
        data["codeforces_username"] if "codeforces_username" in data else None
    )
    kattis_username = data["kattis_username"] if "kattis_username" in data else None
    db, close = get_db()
    add_person(db, person_id, display_name)
    if codeforces_username:
        upsert_platform_login(db, person_id, codeforces_username, "codeforces")
    if kattis_username:
        upsert_platform_login(db, person_id, kattis_username, "kattis")
    close()
    return "ok", 200

@person.route("/get_users")
def get_users():
    db, close = get_db()
    users = get_all_users(db)
    close()
    result = []
    for u in users:
        user = {}
        user["id"] = u[0]
        user["display_name"] = u[1]
        user["kattis_username"] = u[2]
        user["codeforces_username"] = u[3]
        cf = {}
        kattis = {}
        for problem, value in u[4].items():
            if value["platform"] == "codeforces":
                cf[problem] = { 'type': value["type"], 'time': value["time"]}
            else:
                kattis[problem] = value["time"]
        user["kattis_submissions"] = kattis
        user["codeforces_submissions"] = cf
        result.append(user)
    return json.dumps(result)

