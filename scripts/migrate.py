from environment import DATABASE_URL
import psycopg2
from datetime import datetime
from data.platform import add_platform, add_platform_account
from data.person import add_person
from data.crawler import upsert_crawler
from data.problem import upsert_problems
from data.submission import upsert_submissions

con = psycopg2.connect(DATABASE_URL)
cur = con.cursor()

from google.cloud import firestore
db = firestore.Client()

platforms = [["kattis", "Kattis"], ["codeforces", "Codeforces"]]
print("adding platforms")
for platform in platforms:
    add_platform(cur, *platform)

print("adding users")
users_ref = db.collection("users")
for user in users_ref.stream():
    user_id = user.id
    try:
        user_dict = user.to_dict()
        display_name = user_dict["display_name"]
        last_checked_number = user_dict["last_checked"] if "last_checked" in user_dict else 0
        last_checked = datetime.fromtimestamp(last_checked_number)
        add_person(cur, user_id, display_name, last_checked)

        for [platform, _] in platforms:
            key = f"{platform}_username"
            if key in user_dict and user_dict[key].strip():
                username = user_dict[key].strip()
                add_platform_account(cur, user_id, platform, username)
                
    except Exception as e:
        print(f"Error processing user {user_id}: {str(e)}")

print("adding crawlers")
crawlers_ref = db.collection("crawlers")
for crawler in crawlers_ref.stream():
    id = crawler.id
    page = crawler.to_dict()["page"]
    upsert_crawler(cur, id, page)

problems = []

print("adding problems")
for [platform, _] in platforms:
    problems_ref = db.collection(f"{platform}_problems")
    for page in problems_ref.stream():
        page_dict = page.to_dict()
        for [problem, value] in page_dict.items():
            rating = value["rating"] if "rating" in value else None
            problems.append((problem, platform, rating, value["name"]))
upsert_problems(cur, problems)


all_submissions = []

print("adding codeforces submissions")
submissions_ref = db.collection("codeforces")
for submissions in submissions_ref.stream():
    username = submissions.id
    submissions_dict = submissions.to_dict()
    for [problem_id, submission] in submissions_dict.items():
        if problem_id == "contests": continue
        all_submissions.append((problem_id, "codeforces", username, datetime.fromtimestamp(submission["time"]), "AC", submission["type"]))

upsert_submissions(cur, all_submissions)

print("adding kattis submissions")
all_submissions = []
submissions_ref = db.collection("kattis")
for submissions in submissions_ref.stream():
    username = submissions.id
    submissions_dict = submissions.to_dict()
    for [problem_id, time] in submissions_dict.items():
        all_submissions.append((problem_id, "kattis", username, datetime.fromtimestamp(time), "AC", None))

upsert_submissions(cur,all_submissions)

print("finished")
con.commit()
cur.close()
con.close()
