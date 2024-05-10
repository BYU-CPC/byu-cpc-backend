from random import randint, uniform
from datetime import timedelta
from datetime import datetime as dt


def get_name():
    name = "".join(chr(randint(0, 25) + ord("a")) for _ in range(randint(4, 12)))
    name = name[0].upper() + name[1:]
    return name


def mock_time():
    return (dt.now() + timedelta(days=randint(-30, 0))).timestamp()


def mock_kattis():
    return {
        "id": get_name(),
        "timestamp": mock_time(),
        "difficulty": round(uniform(1.2, 9.8), 1),
    }


def mock_cf():
    return {
        "id": get_name(),
        "timestamp": mock_time(),
        "difficulty": randint(800, 2500),
    }


def get_kattis_data():
    return [mock_kattis() for _ in range(randint(0, 12))]


def get_cf_data():
    return {
        "problems": [mock_cf() for _ in range(randint(0, 15))],
        "contests": [
            {"id": get_name(), "timestamp": mock_time()} for _ in range(randint(0, 6))
        ],
    }


def mock_user():
    return {
        "id": get_name() + get_name(),
        "firstName": get_name(),
        "lastName": get_name(),
        "kattis_id": get_name() + get_name(),
        "cf_id": get_name() + get_name(),
        "kattis_data": get_kattis_data(),
        "cf_data": get_cf_data(),
    }
