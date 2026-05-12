import requests
import sys
import json
import datetime

# --- Configuration ---
KEYCLOAK_URL = "http://localhost:8180"
MOVIES_SERVICE_URL = "http://localhost:5002"

REALM = "cinema-realm"
CLIENT_ID = "cinema-client"
CLIENT_SECRET = "gadh2vf!fh5_Asdg34"

# Editor credentials
USERNAME = "editor-user"
PASSWORD = "editor123"

# --- 1. Keycloak Admin Helpers ---
def get_admin_token():
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    payload = {
        "client_id": "admin-cli",
        "username": "admin",
        "password": "admin",
        "grant_type": "password"
    }
    resp = requests.post(url, data=payload)
    resp.raise_for_status()
    return resp.json()["access_token"]

def create_user_if_missing(admin_token, username, password):
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    # Check if exists
    search_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users"
    if requests.get(search_url, params={"username": username}, headers=headers).json():
        print(f"[*] User {username} exists.")
        return

    # Create
    user_data = {
        "username": username, "enabled": True, "email": f"{username}@test.com", "firstName": username, "lastName": "Test",
        "credentials": [{"type": "password", "value": password, "temporary": False}]
    }
    resp = requests.post(search_url, json=user_data, headers=headers)
    if resp.status_code == 201: print(f"[+] Created user: {username}")
    else: print(f"[-] Failed {username}: {resp.text}")

# --- 2. Editor Helpers ---
def get_editor_token():
    try:
        resp = requests.post(f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "username": USERNAME, "password": PASSWORD, "grant_type": "password"
        })
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        print(f"FATAL: Could not login as editor: {e}")
        sys.exit(1)

def add_room(token, number, rows, cols):
    resp = requests.post(f"{MOVIES_SERVICE_URL}/rooms",
                         json={"number": number, "rows": rows, "cols": cols},
                         headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 201: print(f"[+] Room {number} created.")

def add_movie(token, title, duration, desc):
    resp = requests.post(f"{MOVIES_SERVICE_URL}/movies",
                         json={"title": title, "duration": duration, "description": desc},
                         headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 201:
        mid = resp.json()["data"]["id"]
        print(f"[+] Movie {title} created (ID: {mid}).")
        return mid
    return None

def add_screening(token, movie_id, room, date, time):
    resp = requests.post(f"{MOVIES_SERVICE_URL}/movies/{movie_id}/screenings",
                  json={"room_number": room, "date": date, "time": time},
                  headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 201:
        print(f"    [+] Screening added: {date} {time} @ {room}")
    elif resp.status_code != 409:
        print(f"    [-] Screening failed: {resp.text}")

# --- Main ---
def main():
    print("--- Pupulating Data ---")

    # A) Editor Actions
    token = get_editor_token()

    # Rooms
    [add_room(token, r, x, y) for r, x, y in [("A1", 10, 15), ("B2", 8, 12), ("VIP", 5, 8)]]

    # Dynamically calculate future dates to avoid 'expired' screening filter
    today = datetime.date.today()
    d1 = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d") # Tomorrow
    d2 = (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    d3 = (today + datetime.timedelta(days=3)).strftime("%Y-%m-%d")

    # Movies & Screenings
    movies = [
        ("Inception", 148, "Dreams.", [("A1", d1, "18:00"), ("A1", d1, "21:00"), ("VIP", d2, "20:00")]),
        ("The Matrix", 136, "Simulation.", [("B2", d1, "19:30"), ("B2", d3, "15:00")]),
        ("Interstellar", 169, "Space.", [("A1", d2, "14:00"), ("VIP", d3, "19:00")])
    ]

    for title, dura, desc, screenings in movies:
        mid = add_movie(token, title, dura, desc)
        if mid:
            for s in screenings: add_screening(token, mid, *s)

    try:
        adm = get_admin_token()
        for i in range(1, 5): create_user_if_missing(adm, f"user{i}", "password123")
    except Exception as e:
        print(f"[-] Admin tasks failed: {e}")

    print("--- Done ---")

if __name__ == "__main__":
    main()
