from flask import Blueprint, request
from time import sleep
from datetime import datetime
from data.utils import get_db
from data.submission import upsert_submissions
from data.person import refresh_and_get_oldest_codeforces_users
import requests

submission = Blueprint("submission", __name__)
@submission.route("/kattis_submit", methods=["POST"])
def kattis_submit():
    db, close = get_db()
    data = request.json
    username = data["username"]
    submissions = []
    for submission in data["submissions"]:
        external_id = submission["problemId"]
        time = datetime.fromtimestamp(submission["timestamp"] / 1000)
        submissions.append((external_id, "kattis", username, time, "AC", None))
    upsert_submissions(db, submissions)
    close()
    return "ok"

def check_user(username, last_checked):
    url = f"https://codeforces.com/api/user.status?handle={username}"
    response = requests.get(url)
    submissions = []
    if response.status_code == 200:
        content = response.json()
        for submission in content["result"]:
            submit_time = datetime.fromtimestamp(submission["creationTimeSeconds"])
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
            submit_type = submission["author"]["participantType"].lower()
            submissions.append((problem_id, "codeforces", username, submit_time, "AC", submit_type))

@submission.route("/check_users", methods=["GET"])
def check_users():
    db, close = get_db()
    users = refresh_and_get_oldest_codeforces_users(db)
    for user in users:
        try:
            check_user(*user)
            sleep(1)  # so codeforces doesn't rate limit
        except Exception as e:
            print("Error checking user", *user, e)
    return "ok"

