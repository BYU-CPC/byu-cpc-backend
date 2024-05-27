from datetime import datetime as dt
from datetime import timedelta
from math import sqrt
import pytz

START = dt.fromisoformat("2024-05-21T00:00:00.0").replace(
    tzinfo=pytz.timezone("US/Mountain")
)
END = dt.fromisoformat("2024-09-12T18:00:00.0").replace(
    tzinfo=pytz.timezone("US/Mountain")
)

DIFFICULTY_EXPO = 1.2


def get_day_from_timestamp(t):
    return (
        dt.fromtimestamp(t).replace(tzinfo=pytz.timezone("US/Mountain")) - START
    ).days


def get_weekday_from_day(d):
    return (START + timedelta(days=d)).weekday()


def get_days(user):
    timestamps = [
        d["timestamp"]
        for d in user["kattis_data"]
        + user["cf_data"]["problems"]
        + user["cf_data"]["contests"]
    ]
    return {get_day_from_timestamp(t) for t in timestamps}


def skippable(day):
    return get_weekday_from_day(day) == 6


def get_cur_streak(days):
    today = get_day_from_timestamp(dt.now().timestamp())
    count = 1 if today in days else 0
    today -= 1
    while today in days or skippable(today):
        if today in days:
            count += 1
        today -= 1
    return count


def get_max_streak(days):
    best = 0
    cur = 0
    for i in sorted(days):
        if i - 1 in days:
            cur += 1
        # let people take a break on Sundays without ending their streak
        elif not skippable(i - 1):
            cur = 1
        best = max(cur, best)
    return best


def kattis_difficulty_to_exp(d):
    return d**DIFFICULTY_EXPO * 10


def cf_difficulty_to_exp(d):
    return kattis_difficulty_to_exp((1 / 25 * d - 17) / 10)


def get_kattis_exp(user, exp):
    for problem in user["kattis_data"]:
        day = get_day_from_timestamp(problem["timestamp"])
        if day not in exp:
            exp[day] = 0.0
        exp[day] += kattis_difficulty_to_exp(problem["difficulty"])
    return exp


def get_cf_exp(user, exp):
    for problem in user["cf_data"]["problems"]:
        day = get_day_from_timestamp(problem["timestamp"])
        if day not in exp:
            exp[day] = 0.0
        exp[day] += cf_difficulty_to_exp(problem["difficulty"])
    for contest in user["cf_data"]["contests"]:
        day = get_day_from_timestamp(contest["timestamp"])
        if day not in exp:
            exp[day] = 0.0
        exp[day] += 100
    return exp


def get_exp_by_day(user):
    exp = {}
    exp = get_kattis_exp(user, exp)
    exp = get_cf_exp(user, exp)
    for day in exp:
        exp[day] += 10
    return exp


def get_is_active(days):
    return get_day_from_timestamp(dt.now().timestamp()) in days


# total exp e required to get to level l: e = l*100+((l-1)*l/2)*5
# reverse: l = (-195 + sqrt(38025 + 40 * e)) / 10
def get_exp_from_level(level):
    return level * 100 + ((level - 1) * level / 2) * 5


def get_level(exp):
    level = int((-195 + sqrt(38025 + 40 * exp)) / 10)
    next_level = get_exp_from_level(level + 1) - exp
    return level, round(next_level), round(exp - get_exp_from_level(level))


def is_timestamp_in_contest(timestamp):
    return (
        START
        < dt.fromtimestamp(timestamp).replace(tzinfo=pytz.timezone("US/Mountain"))
        < END
    )


def get_table_info(user):
    days = get_days(user)
    user["cur_streak"] = get_cur_streak(days)
    user["max_streak"] = get_max_streak(days)
    user["days"] = sorted(days)
    user["exp"] = get_exp_by_day(user)
    user["score"] = round(sum(user["exp"].values()))
    user["is_active"] = get_is_active(days)
    level, next_level, cur_exp = get_level(user["score"])
    user["level"] = level
    user["next_level"] = next_level
    user["cur_exp"] = cur_exp
    return user
