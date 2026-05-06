import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from flask import Flask

import person
import problem
import submission as submission_module


FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, status_code=200, text=None, json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data

    def json(self):
        return self._json_data


def load_json(name):
    with (FIXTURES / name).open() as fixture:
        return json.load(fixture)


def load_text(name):
    return (FIXTURES / name).read_text()


@contextmanager
def fake_db():
    yield Mock(name="cursor")


@pytest.fixture
def app():
    return Flask(__name__)


def test_update_codeforces_problems_parses_problemset_api_response(monkeypatch):
    mock_get = Mock(return_value=FakeResponse(
        json_data=load_json("codeforces_problemset.json"),
    ))
    mock_upsert_problems = Mock()

    monkeypatch.setattr(problem.requests, "get", mock_get)
    monkeypatch.setattr(problem, "get_db", lambda: fake_db())
    monkeypatch.setattr(problem, "upsert_problems", mock_upsert_problems)

    assert problem.update_codeforces_problems() == "ok"

    mock_get.assert_called_once_with("https://codeforces.com/api/problemset.problems")
    mock_upsert_problems.assert_called_once()
    parsed_problems = mock_upsert_problems.call_args.args[1]
    assert parsed_problems == [
        ("4A", "codeforces", 800, "Watermelon"),
        ("71A", "codeforces", 800, "Way Too Long Words"),
    ]


def test_update_kattis_problems_parses_problem_page_html(monkeypatch):
    mock_get = Mock(return_value=FakeResponse(
        text=load_text("kattis_problems_page.html"),
    ))
    mock_upsert_problems = Mock()
    mock_upsert_crawler = Mock()

    monkeypatch.setattr(problem.requests, "get", mock_get)
    monkeypatch.setattr(problem, "get_db", lambda: fake_db())
    monkeypatch.setattr(problem, "get_crawler", Mock(return_value=7))
    monkeypatch.setattr(problem, "upsert_problems", mock_upsert_problems)
    monkeypatch.setattr(problem, "upsert_crawler", mock_upsert_crawler)

    assert problem.update_kattis_problems() == "ok"

    mock_get.assert_called_once_with("https://open.kattis.com/problems?page=7")
    mock_upsert_problems.assert_called_once()
    parsed_problems = mock_upsert_problems.call_args.args[1]
    assert parsed_problems == [
        ("hello", "kattis", 1.4, "Hello World!"),
        ("carrots", "kattis", 1.9, "Solving for Carrots"),
    ]
    mock_upsert_crawler.assert_called_once()
    assert mock_upsert_crawler.call_args.args[1:] == ("kattis", 8)


def test_update_kattis_problems_resets_crawler_when_page_has_no_problems(monkeypatch):
    mock_get = Mock(return_value=FakeResponse(text="<html><tbody></tbody></html>"))
    mock_upsert_problems = Mock()
    mock_upsert_crawler = Mock()

    monkeypatch.setattr(problem.requests, "get", mock_get)
    monkeypatch.setattr(problem, "get_db", lambda: fake_db())
    monkeypatch.setattr(problem, "get_crawler", Mock(return_value=7))
    monkeypatch.setattr(problem, "upsert_problems", mock_upsert_problems)
    monkeypatch.setattr(problem, "upsert_crawler", mock_upsert_crawler)

    assert problem.update_kattis_problems() == "ok"

    mock_upsert_problems.assert_called_once()
    assert mock_upsert_problems.call_args.args[1] == []
    assert mock_upsert_crawler.call_args.args[1:] == ("kattis", 1)


def test_check_user_parses_only_new_single_author_accepted_submissions(monkeypatch):
    mock_get = Mock(return_value=FakeResponse(
        json_data=load_json("codeforces_user_status.json"),
    ))
    monkeypatch.setattr(submission_module.requests, "get", mock_get)

    submissions = submission_module.check_user(
        "tourist",
        datetime.fromtimestamp(1695000000),
    )

    mock_get.assert_called_once_with("https://codeforces.com/api/user.status?handle=tourist")
    assert submissions == [
        ("4A", "codeforces", "tourist", datetime.fromtimestamp(1700000000), "AC", "practice"),
    ]


def test_check_user_returns_empty_list_for_failed_response(monkeypatch):
    mock_get = Mock(return_value=FakeResponse(status_code=500))
    monkeypatch.setattr(submission_module.requests, "get", mock_get)

    submissions = submission_module.check_user("tourist", datetime.fromtimestamp(0))

    assert submissions == []


def test_validate_codeforces_username_uses_user_info_api(app, monkeypatch):
    mock_get = Mock(return_value=FakeResponse(
        json_data=load_json("codeforces_user_info.json"),
    ))
    monkeypatch.setattr(person.requests, "get", mock_get)

    with app.test_request_context(
        "/validate_username",
        method="POST",
        json={"username": "tourist", "platform": "codeforces"},
    ):
        response = person.validate_username()

    mock_get.assert_called_once_with("https://codeforces.com/api/user.info?handles=tourist")
    assert response == {"valid": True}


def test_validate_kattis_username_uses_profile_page(app, monkeypatch):
    mock_get = Mock(return_value=FakeResponse(
        text=load_text("kattis_user_profile.html"),
    ))
    monkeypatch.setattr(person.requests, "get", mock_get)

    with app.test_request_context(
        "/validate_username",
        method="POST",
        json={"username": "tourist", "platform": "kattis"},
    ):
        response = person.validate_username()

    mock_get.assert_called_once_with("https://open.kattis.com/users/tourist")
    assert response == {"valid": True}


def test_validate_username_returns_false_for_not_found_profile(app, monkeypatch):
    mock_get = Mock(return_value=FakeResponse(status_code=404))
    monkeypatch.setattr(person.requests, "get", mock_get)

    with app.test_request_context(
        "/validate_username",
        method="POST",
        json={"username": "missing-user", "platform": "kattis"},
    ):
        response = person.validate_username()

    assert response == {"valid": False}
