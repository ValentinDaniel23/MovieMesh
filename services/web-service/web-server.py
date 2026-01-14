
import os
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash

from utils import (
    decode_and_verify_access_token, extract_roles, wait_for_keycloak,
    AUTH_SERVICE_URL, MOVIES_SERVICE_URL, TICKET_SERVICE_URL, PORT, FLASK_SECRET_KEY
)

load_dotenv()

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

def get_user_info():
    access_token = request.cookies.get("access_token")
    user = None
    roles = []

    if access_token:
        try:
            user = decode_and_verify_access_token(access_token)
            roles = sorted(extract_roles(user))
        except Exception as e:
            print(f"[AUTH ERROR] Token validation failed: {e}", flush=True)
            pass
    else:
        if not request.path.startswith("/static"):
             print(f"[AUTH DEBUG] No access_token cookie found for {request.path}", flush=True)

    return user, roles, access_token

def backend_request(method, endpoint, json=None):
    _, _, token = get_user_info()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{MOVIES_SERVICE_URL}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=json, timeout=5)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=json, timeout=5)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=5)

        try:
            return resp.json(), resp.status_code
        except ValueError:
            print(f"Non-JSON response from {url}: {resp.text}")
            return {"ok": False, "error": f"Backend Error (Not JSON): {resp.text[:200]}"}, resp.status_code

    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

@app.get("/")
def home():
    user, roles, _ = get_user_info()
    return render_template("home.html", auth_service_url=AUTH_SERVICE_URL, user=user, roles=roles)

@app.get("/dashboard")
def dashboard():
    user, roles, _ = get_user_info()
    return render_template("dashboard.html", auth_service_url=AUTH_SERVICE_URL, user=user, roles=roles)


# --- MOVIES ---

@app.route("/movies")
def movies_list():
    user, roles, _ = get_user_info()
    resp, code = backend_request("GET", "/movies")
    movies = resp.get("data", []) if code == 200 else []
    return render_template("movies_list.html", movies=movies, user=user, roles=roles, auth_service_url=AUTH_SERVICE_URL)

@app.route("/movies/<mid>")
def movie_details(mid):
    user, roles, _ = get_user_info()

    m_resp, m_code = backend_request("GET", f"/movies/{mid}")
    if m_code != 200:
        return f"Error loading movie: {m_resp.get('error')}", m_code

    s_resp, s_code = backend_request("GET", f"/movies/{mid}/screenings")
    screenings = s_resp.get("data", []) if s_code == 200 else []

    r_resp, r_code = backend_request("GET", "/rooms")
    all_rooms = r_resp.get("data", []) if r_code == 200 else []

    return render_template("movie_details.html",
                           movie=m_resp["data"],
                           screenings=screenings,
                           all_rooms=all_rooms,
                           user=user, roles=roles, auth_service_url=AUTH_SERVICE_URL)


# --- ADMIN: MOVIES ---

@app.route("/movies/add", methods=["POST"])
def add_movie():
    title = request.form.get("title")
    duration = request.form.get("duration")
    description = request.form.get("description")

    if not title or not duration:
        flash("Title and Duration are required")
        return redirect(url_for("movies_list"))

    payload = {
        "title": title,
        "duration": int(duration),
        "description": description
    }
    resp, code = backend_request("POST", "/movies", json=payload)
    if code == 201:
        flash("Movie added!")
    else:
        flash(f"Error: {resp.get('error')}")
    return redirect(url_for("movies_list"))

@app.route("/movies/<mid>/delete", methods=["POST"])
def delete_movie(mid):
    resp, code = backend_request("DELETE", f"/movies/{mid}")
    if code == 200:
        flash("Movie deleted!")
    else:
        flash(f"Error: {resp.get('error')}")
    return redirect(url_for("movies_list"))


# --- ADMIN: SCREENINGS ---

@app.route("/movies/<mid>/screenings/add", methods=["POST"])
def add_screening(mid):
    room_number = request.form.get("room_number")
    date = request.form.get("date")
    time = request.form.get("time")

    payload = {"room_number": room_number, "date": date, "time": time}
    resp, code = backend_request("POST", f"/movies/{mid}/screenings", json=payload)

    if code == 201:
        flash("Screening added!")
    else:
        flash(f"Error adding screening: {resp.get('error')}")
    return redirect(url_for("movie_details", mid=mid))

@app.route("/movies/<mid>/screenings/<sid>/delete", methods=["POST"])
def delete_screening(mid, sid):
    resp, code = backend_request("DELETE", f"/movies/{mid}/screenings/{sid}")
    if code != 200:
        flash(f"Error: {resp.get('error')}")
    return redirect(url_for("movie_details", mid=mid))


# --- ROOMS ---

@app.route("/rooms")
def rooms_list():
    user, roles, _ = get_user_info()
    resp, code = backend_request("GET", "/rooms")
    rooms = resp.get("data", []) if code == 200 else []
    return render_template("rooms_list.html", rooms=rooms, user=user, roles=roles, auth_service_url=AUTH_SERVICE_URL)

@app.route("/rooms/add", methods=["POST"])
def add_room():
    number = request.form.get("number")
    rows = request.form.get("rows")
    cols = request.form.get("cols")

    payload = {"number": number, "rows": int(rows), "cols": int(cols)}
    resp, code = backend_request("POST", "/rooms", json=payload)

    if code == 201:
        flash("Room added!")
    else:
        flash(f"Error: {resp.get('error')}")
    return redirect(url_for("rooms_list"))


# --- SEATS ---

@app.route("/movies/<mid>/screenings/<sid>/seats")
def seat_map(mid, sid):
    user, roles, _ = get_user_info()

    resp, code = backend_request("GET", f"/movies/{mid}/screenings/{sid}/seats")
    if code != 200:
        return f"Error: {resp.get('error')}", code

    data = resp["data"]
    return render_template("seat_map.html",
                           user=user, roles=roles,
                           data=data, auth_service_url=AUTH_SERVICE_URL,
                           mid=mid, sid=sid)

@app.route("/reservations", methods=["POST"])
def proxy_reservation():
    user, roles, _ = get_user_info()
    if not user:
        return {"error": "Not authenticated"}, 401

    payload = request.json
    resp, code = backend_request("POST", "/reservations", json=payload)
    return resp, code

@app.route("/myprofile")
def my_profile():
    user, roles, _ = get_user_info()
    if not user:
        return redirect(f"{AUTH_SERVICE_URL}/auth/signin")

    resp, code = backend_request("GET", "/reservations/me")
    reservations = resp.get("data", []) if code == 200 else []

    return render_template("my_profile.html", user=user, roles=roles, reservations=reservations, auth_service_url=AUTH_SERVICE_URL, ticket_service_url=TICKET_SERVICE_URL)

@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    wait_for_keycloak()
    app.run(host="0.0.0.0", port=int(PORT), debug=True)

