from flask_cors import cross_origin
from bs4 import BeautifulSoup
from flask import Blueprint
from data.utils import get_db
from data.problem import get_all_problems as get_problems, upsert_problems
from data.crawler import get_crawler, upsert_crawler
import requests


problem = Blueprint("problem", __name__)


@problem.route("/get_all_problems")
@cross_origin()
def get_all_problems():
    [db, close] = get_db()
    result = {}
    problems = get_problems(db)
    close()
    for external_id, platform_id, rating, name in problems:
        if platform_id not in result:
            result[platform_id] = {}
        result[platform_id][external_id] = {"name": name, "rating": rating}
    return result



@problem.route("/update_codeforces_problems")
def update_codeforces_problems():
    url = "https://codeforces.com/api/problemset.problems"
    response = requests.get(url)
    if response.status_code == 200:
        [db, close] = get_db()
        problems = []
        response_content = response.json()
        for problem in response_content["result"]["problems"]:
            if "contestId" in problem:
                problem_id = f"{problem['contestId']}{problem['index']}"
            else:
                continue
            rating = problem["rating"] if "rating" in problem else None
            name = problem["name"]
            problems.append((problem_id, "codeforces", rating, name))
        upsert_problems(db, problems)
        close()
    return "ok"


@problem.route("/update_kattis_problems")
def update_kattis_problems():
    [db, close] = get_db()
    n = get_crawler(db,"kattis")
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
                    problem_id = problem_link["href"].strip().split("/")[-1]
                    difficulty_text = difficulty_data.text.strip()
                    if "-" in difficulty_text:
                        difficulty = difficulty_text.split("-")[1].strip()
                    else:
                        difficulty = difficulty_text
                    problems.append((problem_id, "kattis", float(difficulty), problem_link.contents[0]))
        next_page = n + 1 if problems else 1
        upsert_crawler(db, "kattis", next_page)
        close()
    return "ok"
