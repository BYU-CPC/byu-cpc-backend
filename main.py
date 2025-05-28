from flask import Flask
from flask_cors import CORS
from firebase_admin import initialize_app
import os, time
from problem import problem
from submission import submission
from person import person
from leaderboard import leaderboard

os.environ["TZ"] = "US/Mountain"
time.tzset()

initialize_app()

app = Flask(__name__)
app.register_blueprint(problem)
app.register_blueprint(leaderboard)
app.register_blueprint(submission)
app.register_blueprint(person)

cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"


@app.route("/ping")
def ping():
    return "pong", 200


if __name__ == "__main__":
    app.run()

