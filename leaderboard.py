from google.cloud import firestore
from flask import Blueprint
import json

db = firestore.Client()


leaderboard = Blueprint("leaderboard", __name__)


@leaderboard.route("/leaderboard/<leaderboard_name>")
def get_leaderboard(leaderboard_name):
    return json.dumps(
        db.collection("leaderboard")
        .document(leaderboard_name if leaderboard_name else "all")
        .get()
        .to_dict()
    )


@leaderboard.route("/leaderboard")
def get_leaderboard_index():
    return json.dumps(db.collection("leaderboard").document("index").get().to_dict())
