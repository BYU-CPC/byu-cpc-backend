from flask import Flask, request
from flask_cors import CORS, cross_origin
from google.cloud import firestore
from firebase_admin import auth
import firebase_admin
import os, time
from bs4 import BeautifulSoup
import requests
import json
from datetime import datetime as dt
import pytz
from problem import problem
from platforms import supported_platforms

os.environ["TZ"] = "US/Mountain"
time.tzset()
firebase_admin.initialize_app()
app = Flask(__name__)
app.register_blueprint(problem)
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"


db = firestore.Client()
problem_cache = {}
all_study_problems = {"kattis": set(), "codeforces": set()}
this_week = {}


def get_study_problems():
    global this_week, all_study_problems
    all_study_problems = {"kattis": set(), "codeforces": set()}
    week_ref = db.collection("week")
    newest = 0
    for doc in week_ref.stream():
        week = doc.to_dict()
        week_id = week["start"]
        week_start = (
            dt.fromisoformat(week_id + "T00:00:00.0")
            .replace(tzinfo=pytz.timezone("US/Mountain"))
            .timestamp()
        )
        if dt.now().timestamp() > week_start:
            if week_start > newest:
                newest = week_start
                this_week = week
            for platform in all_study_problems:
                if platform in week:
                    all_study_problems[platform] |= set(week[platform])


get_study_problems()


def get_username():
    return auth.verify_id_token(request.json["id_token"])["uid"]


def is_logged_in():
    username = get_username()
    if username:
        return True
    return False


@app.route("/get_users")
def get_users():
    users_ref = db.collection("users")
    users = []
    for user in users_ref.stream():
        user_dict = user.to_dict()
        user_dict["id"] = user.id
        for platform in supported_platforms:
            key = f"{platform}_username"
            submissions = {}
            if key in user_dict and user_dict[key]:
                username = user_dict[key]
                submissions = db.collection(platform).document(username).get().to_dict()
            user_dict[f"{platform}_submissions"] = submissions
        users.append(user_dict)
    return json.dumps(users)


@app.route("/kattis_submit", methods=["POST"])
@cross_origin()
def kattis_submissions():
    data = request.json
    submissions_ref = db.collection("kattis").document(data["username"])
    submissions = submissions_ref.get().to_dict()
    if not submissions:
        submissions = {}
    change = False
    for problem in data["submissions"]:
        problem_id = problem["problemId"]
        timestamp = problem["timestamp"] / 1000
        if problem_id not in submissions or submissions[problem_id] > timestamp:
            change = True
            submissions[problem_id] = timestamp
    if change:
        submissions_ref.set(submissions)
    return "ok", 200


def check_user(user_dict):
    codeforces_username = user_dict["codeforces_username"]
    last_checked = user_dict["last_checked"]
    change = False
    if codeforces_username:
        submissions_ref = db.collection("codeforces").document(codeforces_username)
        past_submissions = submissions_ref.get().to_dict()
        if not past_submissions:
            past_submissions = {"contests": {}}
        url = f"https://codeforces.com/api/user.status?handle={codeforces_username}"
        response = requests.get(url)
        if response.status_code == 200:
            content = response.json()
            submissions = content["result"]
            for submission in submissions:
                submit_time = submission["creationTimeSeconds"]
                if (
                    submit_time < last_checked
                    or submission["verdict"] != "OK"
                    or len(submission["author"]["members"]) > 1
                ):
                    continue
                prefix = (
                    submission["problem"]["contestId"]
                    if "contestId" in submission["problem"]
                    else submission["problem"]["problemsetName"]
                )
                problem_id = str(prefix) + str(submission["problem"]["index"])
                if (
                    problem_id not in past_submissions
                    or submit_time < past_submissions[problem_id]["time"]
                ):
                    change = True
                    past_submissions[problem_id] = {
                        "time": submit_time,
                        "type": submission["author"]["participantType"].lower(),
                    }
                    if submission["author"]["participantType"] == "CONTESTANT":
                        past_submissions["contests"][
                            str(submission["contestId"])
                        ] = submit_time
        if change:
            submissions_ref.set(past_submissions)


@app.route("/check_users", methods=["GET"])
def check_users():
    users_ref = db.collection("users")
    query = users_ref.order_by(
        "last_checked", direction=firestore.Query.ASCENDING
    ).limit(5)
    results = query.stream()
    for user in results:
        user_dict = user.to_dict()
        try:
            check_user(user_dict)
            users_ref.document(user.id).update({"last_checked": dt.now().timestamp()})
            time.sleep(1)  # so codeforces doesn't rate limit
        except:
            print("Error checking user", user.id)
    return "ok"


@app.route("/create_user", methods=["POST"])
def create_user():
    if is_logged_in():
        data = request.json
        username = get_username()
        user_ref = db.collection("users").document(username)
        display_name = data["display_name"]
        codeforces_username = (
            data["codeforces_username"] if "codeforces_username" in data else ""
        )
        kattis_username = data["kattis_username"] if "kattis_username" in data else ""
        document = {
            "display_name": display_name,
            "kattis_username": kattis_username,
            "codeforces_username": codeforces_username,
        }

        user_ref.set(document)
        return "ok", 200
    return "not signed in", 400


@app.route("/set_kattis_username", methods=["POST"])
def set_kattis_username():
    # invalidate_cache()
    if is_logged_in():
        username = get_username()
        kattis_username = request.json["username"]
        user_ref = db.collection("users").document(username)
        user_ref.update({"kattis_username": kattis_username, "last_checked": 0})
        return "ok", 200
    return "not signed in", 400


@app.route("/set_codeforces_username", methods=["POST"])
def set_codeforces_username():
    # invalidate_cache()
    if is_logged_in():
        username = get_username()
        codeforces_username = request.json["username"]
        user_ref = db.collection("users").document(username)
        user_ref.update({"codeforces_username": codeforces_username, "last_checked": 0})
        return "ok", 200
    return "not signed in", 400


@app.route("/get_profile", methods=["POST"])
def get_profile():
    if is_logged_in():
        username = get_username()
        user_data = db.collection("users").document(username).get().to_dict()
        return json.dumps(user_data), 200
    return "not signed in", 400


@app.route("/kattis/validate", methods=["POST"])
def kattis_validate():
    username = request.json["username"]
    url = f"https://open.kattis.com/users/{username}"
    response = requests.get(url)
    return {"valid": response.status_code == 200}


@app.route("/codeforces/validate", methods=["POST"])
def codeforces_validate():
    username = request.json["username"]
    url = f"https://codeforces.com/api/user.info?handles={username}"
    response = requests.get(url)
    return {"valid": response.status_code == 200}


@app.route("/get_this_week")
def get_this_week():
    get_study_problems()
    return json.dumps(this_week)


@app.route("/get_all_study_problems")
def get_all_study_problems():
    get_study_problems()
    serializable = {key: list(all_study_problems[key]) for key in all_study_problems}
    return json.dumps(serializable)


@app.route("/ping")
def ping():
    return "pong", 200


@app.route("/test")
def test():
    test_ref = db.collection("test").document("test")
    test = test_ref.get().to_dict()
    print(test)
    return "ok"


if __name__ == "__main__":
    app.run()
