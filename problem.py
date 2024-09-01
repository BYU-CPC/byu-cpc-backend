from collections import defaultdict
from flask_cors import cross_origin
from bs4 import BeautifulSoup
from google.cloud import firestore
from utils import get_hash_table_index
from platforms import supported_platforms
from flask import Blueprint
import requests

db = firestore.Client()


problem = Blueprint("problem", __name__)


def get_platform_problems(problem_collection_ref):
    all_problems = {}
    for document in problem_collection_ref.stream():
        all_problems.update(document.to_dict())
    return all_problems


@problem.route("/get_all_problems")
@cross_origin()
def get_all_problems():
    return {
        platform: get_platform_problems(db.collection(platform + "_problems"))
        for platform in supported_platforms
    }


@problem.route("/update_codeforces_problems")
def update_codeforces_problems():
    url = "https://codeforces.com/api/problemset.problems"
    response = requests.get(url)
    if response.status_code == 200:
        problems = {}
        response_content = response.json()
        for problem in response_content["result"]["problems"]:
            if "contestId" in problem:
                problem_id = f"{problem['contestId']}{problem['index']}"
            else:
                print(problem)
                continue
            problems[problem_id] = {"name": problem["name"]}
            if "rating" in problem:
                problems[problem_id]["rating"] = problem["rating"]
        update_problems(problems, db.collection("codeforces_problems"))
    return "ok"


@problem.route("/update_kattis_problems")
def update_kattis_problems():
    crawler_page_ref = db.collection("crawlers").document("kattis")
    page = crawler_page_ref.get().to_dict()
    n = page["page"] if page and "page" in page else 1
    url = f"https://open.kattis.com/problems?page={n}"
    response = requests.get(url)
    if response.status_code == 200:
        problems = {}
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
                        problems[problem_id] = {
                            "rating": float(difficulty),
                            "name": problem_link.contents[0],
                        }
                    except:
                        print("problem failed")
        update_problems(problems, db.collection("kattis_problems"))
        next_page = n + 1 if problems else 1
        crawler_page_ref.set({"page": next_page})
    return "ok"


def update_problems(problem_id_to_info, problem_collection_ref):
    index_to_problem_id = defaultdict(list)
    for problem_id in problem_id_to_info:
        index_to_problem_id[get_hash_table_index(problem_id)].append(problem_id)
    for index in index_to_problem_id:
        update_payload = {
            problem_id: problem_id_to_info[problem_id]
            for problem_id in index_to_problem_id[index]
        }
        problem_collection_ref.document(str(index)).set(update_payload, merge=True)
