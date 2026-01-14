
import os
from urllib.parse import urlencode

import requests
from flask import Blueprint, Flask, make_response, redirect, request
from utils import *

app = Flask(__name__)
bp = Blueprint("auth", __name__, url_prefix="/auth")

def _set_cookie(resp, name: str, value: str | None):
    if not value:
        resp.delete_cookie(name, path="/")
        return
    resp.set_cookie(
        name,
        value,
        httponly=True,
        samesite="Lax",
        secure=False,
        path="/",
    )


@bp.get("/signin")
def signin():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": REDIRECT_URI,
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


@bp.get("/register")
def register():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": REDIRECT_URI,
        "kc_action": "register",
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


@bp.get("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return {"ok": False, "error": "No authorization code received"}, 400

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
    }
    if CLIENT_SECRET:
        payload["client_secret"] = CLIENT_SECRET

    try:
        token_resp = requests.post(TOKEN_URL, data=payload, timeout=10)
        token_resp.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Token exchange failed: {exc}"}, 502

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    id_token = token_data.get("id_token")

    if not access_token:
        return {"ok": False, "error": "No access_token returned"}, 502

    try:
        decode_and_verify_access_token(access_token)
    except Exception as exc:
        return {"ok": False, "error": f"Invalid access_token: {exc}"}, 401

    resp = make_response(redirect(POST_LOGIN_REDIRECT_URI))
    print(f"Setting access_token cookie: {access_token[:10]}...", flush=True)
    _set_cookie(resp, "access_token", access_token)
    _set_cookie(resp, "id_token", id_token)
    return resp


@bp.get("/signout")
def signout():
    id_token = request.cookies.get("id_token")
    params = {
        "client_id": CLIENT_ID,
        "post_logout_redirect_uri": POST_LOGOUT_REDIRECT_URI,
    }
    if id_token:
        params["id_token_hint"] = id_token

    resp = make_response(redirect(f"{LOGOUT_URL}?{urlencode(params)}"))
    _set_cookie(resp, "access_token", None)
    _set_cookie(resp, "id_token", None)
    return resp

app.register_blueprint(bp)

@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    wait_for_keycloak()
    app.run(host="0.0.0.0", port=int(PORT), debug=True)

