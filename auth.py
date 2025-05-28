from flask import request
from firebase_admin import auth
def get_user_id(debug=False):
    headers = request.headers
    if headers is None or "Authorization" not in headers: return None
    user_id = auth.verify_id_token(headers["Authorization"])["uid"]
    if debug:print("user_id 1",user_id)
    return user_id


def is_logged_in():
    user_id = get_user_id()
    if user_id:
        return True
    return False
