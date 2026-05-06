import logging
import os, time

import psycopg2
from firebase_admin import initialize_app
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from problem import problem
from submission import submission
from person import person
from leaderboard import leaderboard

os.environ["TZ"] = "US/Mountain"
time.tzset()

initialize_app()

app = Flask(__name__)
logger = logging.getLogger(__name__)


@app.errorhandler(psycopg2.Error)
def handle_database_error(error):
    logger.exception("Database error")
    return jsonify({
        "error": "database_error",
        "message": "A database error occurred.",
    }), 500


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error

    logger.exception("Unexpected error")
    return jsonify({
        "error": "internal_server_error",
        "message": "An unexpected error occurred.",
    }), 500


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

