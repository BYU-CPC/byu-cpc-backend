from flask import request
from firebase_admin import auth
def get_user_id():
    headers = request.headers
    if headers is None or "Authorization" not in headers: return None
    return auth.verify_id_token(headers["Authorization"])["uid"]


def is_logged_in():
    user_id = get_user_id()
    if user_id:
        return True
    return False
