from flask import Flask, request
from flask_cors import CORS, cross_origin
from transform_user import get_table_info, is_timestamp_in_contest
from google.cloud import firestore
from firebase_admin import auth
import firebase_admin
from math import inf
import os, time
from bs4 import BeautifulSoup
import requests
from collections import defaultdict
import json
from datetime import datetime as dt

os.environ["TZ"] = "US/Mountain"
time.tzset()
firebase_admin.initialize_app()
app = Flask(__name__)
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"


db = firestore.Client(project="byu-cpc")
problem_cache = {}


def get_username():
    return auth.verify_id_token(request.json["id_token"])["uid"]


def is_logged_in():
    username = get_username()
    if username:
        return True
    return False


def invalidate_cache():
    db.collection("table").document("cache").set(None)


def calc_table():
    rows = []
    docs = db.collection("users").stream()
    difficulties_ref = db.collection("problems")
    for doc in docs:
        user = doc.to_dict()
        user["id"] = doc.id
        if user["kattis_username"]:
            submissions_ref = db.collection("kattis").document(user["kattis_username"])
            submissions = submissions_ref.get().to_dict()
            if not submissions:
                submissions = {}
            problems = []
            for submission in submissions:
                if not is_timestamp_in_contest(submissions[submission]):
                    continue
                difficulty = 0
                if (
                    submission in problem_cache
                    and dt.now().timestamp() - problem_cache[submission]["timestamp"]
                    < 1000 * 60 * 60 * 24
                ):
                    difficulty = problem_cache[submission]["difficulty"]
                else:
                    difficulty_dict = (
                        difficulties_ref.document(submission).get().to_dict()
                    )
                    difficulty = difficulty_dict["difficulty"] if difficulty_dict else 0
                    if difficulty:
                        problem_cache[submission] = {
                            "difficulty": difficulty,
                            "timestamp": dt.now().timestamp(),
                        }
                problems.append(
                    {
                        "id": submission,
                        "timestamp": submissions[submission],
                        "difficulty": difficulty,
                    }
                )
            user["kattis_data"] = problems
        else:
            user["kattis_data"] = []
        user["cf_data"] = {"contests": [], "problems": []}
        if user["codeforces_username"]:
            submissions_ref = db.collection("codeforces").document(
                user["codeforces_username"]
            )
            submissions = submissions_ref.get().to_dict()
            if not submissions:
                submissions = {"contests": {}}
            problems = []
            for submission in submissions:
                if submission == "contests":
                    user["cf_data"]["contests"] = [
                        {
                            "id": contest_id,
                            "timestamp": submissions[submission][contest_id],
                        }
                        for contest_id in submissions[submission]
                        if is_timestamp_in_contest(submissions[submission][contest_id])
                    ]
                    continue
                if not is_timestamp_in_contest(submissions[submission]["time"]):
                    continue
                difficulty = 800
                if (
                    submission in problem_cache
                    and dt.now().timestamp() - problem_cache[submission]["timestamp"]
                    < 1000 * 60 * 60 * 24
                ):
                    difficulty = problem_cache[submission]["difficulty"]
                else:
                    difficulty_dict = (
                        difficulties_ref.document(submission).get().to_dict()
                    )
                    difficulty = (
                        difficulty_dict["difficulty"] if difficulty_dict else 800
                    )
                    if difficulty:
                        problem_cache[submission] = {
                            "difficulty": difficulty,
                            "timestamp": dt.now().timestamp(),
                        }
                problems.append(
                    {
                        "id": submission,
                        "timestamp": submissions[submission]["time"],
                        "difficulty": difficulty,
                        "type": submissions[submission]["type"],
                    }
                )
            user["cf_data"]["problems"] = problems
        rows.append(get_table_info(user))
    json_rows = json.dumps(rows)
    db.collection("table").document("cache").set({"cache": json_rows, "valid": 1})
    return json_rows


@app.route("/get_table")
def get_table():
    cache = db.collection("table").document("cache").get().to_dict()
    if cache and cache["valid"]:
        print("hit db cache")
        return cache["cache"]
    return calc_table()


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
        invalidate_cache()
    return "ok", 200


def add_codeforces_problem_rating(id, rating):
    if id in problem_cache:
        return
    problem_cache[id] = {"difficulty": rating, "timestamp": dt.now().timestamp()}
    problem_ref = db.collection("problems").document(id)
    problem_ref.set({"difficulty": rating, "platform": "codeforces"})


@app.route("/check_users", methods=["GET"])
def check_users():
    users_ref = db.collection("users")
    query = users_ref.order_by(
        "last_checked", direction=firestore.Query.ASCENDING
    ).limit(5)
    results = query.stream()
    any_change = False
    for user in results:
        user_id = user.id
        user_dict = user.to_dict()
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
                    problem_id = str(submission["problem"]["contestId"]) + str(
                        submission["problem"]["index"]
                    )
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
                        if (
                            "rating" in submission["problem"]
                            and submission["problem"]["rating"]
                        ):
                            add_codeforces_problem_rating(
                                problem_id, submission["problem"]["rating"]
                            )
            if change:
                submissions_ref.set(past_submissions)
                any_change = True
            time.sleep(2)
        users_ref.document(user_id).update({"last_checked": dt.now().timestamp()})
    if any_change:
        invalidate_cache()

    return "ok"


@app.route("/invalidate_users", methods=["GET"])
def invalidate_users():
    users_ref = db.collection("users")
    results = users_ref.stream()
    for user in results:
        users_ref.document(user.id).update({"last_checked": 0})
    return "ok"


@app.route("/check_problems", methods=["GET"])
def check_problems():
    page_ref = db.collection("kattis").document("problem_crawler_page")
    page = page_ref.get().to_dict()
    n = page["page"] if page and "page" in page else 1
    url = f"https://open.kattis.com/problems?page={n}"
    response = requests.get(url)
    if response.status_code == 200:
        problems = []
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")
        for table in soup.find_all("tbody"):
            rows = table.find_all("tr")

            for row in rows:
                problem_link = row.find("a", href=True)
                difficulty_data = row.find("span", class_="difficulty_number")

                if problem_link and difficulty_data:
                    try:
                        problem_id = problem_link["href"].strip().split("/")[-1]
                        difficulty_text = difficulty_data.text.strip()
                        if "-" in difficulty_text:
                            difficulty = difficulty_text.split("-")[1].strip()
                        else:
                            difficulty = difficulty_text
                        problems.append((problem_id, float(difficulty)))
                    except:
                        print("problem failed")
        next_page = n + 1 if problems else 1
        page_ref.set({"page": next_page})
        if problems:
            batch = db.batch()
            for problem_id, difficulty in problems:
                ref = db.collection("problems").document(problem_id)
                data = {"difficulty": difficulty, "platform": "kattis"}
                batch.set(ref, data)
            batch.commit()
    return "ok", 200


@app.route("/create_user", methods=["POST"])
def create_user():
    invalidate_cache()
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
            "contests": {},
            "kattis_username": kattis_username,
            "codeforces_username": codeforces_username,
            "last_checked": 0,
        }

        user_ref.set(document)
        return "ok", 200
    return "not signed in", 400


@app.route("/set_kattis_username", methods=["POST"])
def set_kattis_username():
    invalidate_cache()
    if is_logged_in():
        username = get_username()
        kattis_username = request.json["username"]
        user_ref = db.collection("users").document(username)
        user_ref.update({"kattis_username": kattis_username})
        return "ok", 200
    return "not signed in", 400


@app.route("/set_codeforces_username", methods=["POST"])
def set_codeforces_username():
    invalidate_cache()
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


@app.route("/ping")
def ping():
    return "pong", 200


if __name__ == "__main__":
    app.run()
