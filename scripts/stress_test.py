import concurrent.futures
import requests
import time
import sys

# CONFIG
WEB_SERVICE_URL = "http://localhost:8081"
MOVIES_SERVICE_URL = "http://localhost:5002"

RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"

print(f"{CYAN}--- Cinema App Multi-Seat Stress Test ---{RESET}")
print("This script simulates MULTIPLE users trying to book 5 CONSECUTIVE SEATS sequentially.")
print("For each seat, we verify that exactly 100% ONE success occurs and others FAIL (409 Conflict).\n")

# We will use the 4 users created by populate_data.py: user1, user2, user3, user4

CONFIG_USERS = [
    ("user1", "password123"),
    ("user2", "password123"),
    ("user3", "password123"),
    ("user4", "password123")
]

KEYCLOAK_URL = "http://localhost:8180"
REALM = "cinema-realm"
CLIENT_ID = "cinema-client"
CLIENT_SECRET = "gadh2vf!fh5_Asdg34"

def get_token(username, password):
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": username,
        "password": password,
        "grant_type": "password"
    }
    try:
        resp = requests.post(url, data=payload, timeout=5)
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        print(f"{RED}Login failed for {username}: {e}{RESET}")
        return None

print(f"{CYAN}[0] Logging in users...{RESET}")
USER_TOKENS = []

for u, p in CONFIG_USERS:
    t = get_token(u, p)
    if t:
        USER_TOKENS.append((u, t))
        print(f"Logged in: {u}")
    else:
        print(f"Skipping {u}")

if not USER_TOKENS:
    print(f"{RED}No users logged in. Run populate_data.py first!{RESET}")
    sys.exit(1)

# Grab the first token for discovery
main_token = USER_TOKENS[0][1]
setup_headers = {"Authorization": f"Bearer {main_token}"}

print(f"\n{CYAN}[1] Fetching Movies & Screenings...{RESET}")
try:
    BASE_API = "http://localhost:5002"

    r = requests.get(f"{BASE_API}/movies", headers=setup_headers)
    if r.status_code != 200:
        print(f"{RED}Failed to fetch movies. API returned {r.status_code}.{RESET}")
        sys.exit(1)

    movies = r.json().get("data", [])
    if not movies:
        print(f"{RED}No movies found. Populate DB first.{RESET}")
        sys.exit(1)

    movie = movies[0]
    mid = movie["id"]
    print(f"Selected Movie: {movie['title']}")

    r = requests.get(f"{BASE_API}/movies/{mid}/screenings", headers=setup_headers)
    screenings = r.json().get("data", [])

    if not screenings:
        print(f"{RED}No screenings found for this movie. (Maybe all expired?){RESET}")
        sys.exit(1)

    screening = screenings[0]
    sid = screening["id"]
    print(f"Selected Screening: {screening['date']} {screening['time']} (Room: {screening['room_number']})")

except Exception as e:
    print(f"{RED}Setup Error: {e}{RESET}")
    sys.exit(1)

import itertools

def attempt_booking(args):
    username, access_token, screening_id, row, col = args
    url = f"{BASE_API}/reservations"
    payload = {
        "screening_id": screening_id,
        "seat_row": row,
        "seat_col": col
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        r = requests.post(url, json=payload, headers=headers)
        return username, r.status_code, r.text
    except Exception as e:
        return username, 999, str(e)

def run_test_for_seat(seat_row, seat_col, request_count=20):
    print(f"\n{CYAN}[Test Seat R{seat_row+1}-C{seat_col+1}] Simulating race condition...{RESET}")

    # Create tasks: cycle through users
    user_cycle = itertools.cycle(USER_TOKENS)
    # We pack arguments for attempt_booking
    tasks = []
    for _ in range(request_count):
        u, t = next(user_cycle)
        tasks.append((u, t, sid, seat_row, seat_col))

    results = []
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_booking, t) for t in tasks]
        for future in concurrent.futures.as_completed(futures):
            u, status, text = future.result()
            results.append(status)
            if status == 200:
                print(f"  -> [{u}] {GREEN}SUCCESS (200){RESET}")
            elif status == 409:
                print(f"  -> [{u}] {YELLOW}CONFLICT (409){RESET}")
            else:
                print(f"  -> [{u}] {RED}FAIL ({status}){RESET}")

    duration = time.time() - start_time
    successes = results.count(200)
    conflicts = results.count(409)
    others = len(results) - successes - conflicts

    print(f"  Requests: {request_count} | {GREEN}Success: {successes}{RESET} | {YELLOW}Conflict: {conflicts}{RESET} | {RED}Error: {others}{RESET} | Time: {duration:.2f}s")

    if successes == 1:
        print(f"  {GREEN}>>> PASS: Exactly one booking succeeded. <<< {RESET}")
        return True
    elif successes == 0:
        print(f"  {RED}>>> FAIL: Zero bookings. Seat possibly already taken? <<< {RESET}")
        return False
    else:
        print(f"  {RED}>>> CRITICAL FAIL: {successes} bookings succeeded for same seat! Race condition! <<< {RESET}")
        return False

# MAIN LOOP for 5 seats
print(f"\n{CYAN}[3] Starting 5 Consecutive Seat Tests...{RESET}")

seats_to_test = [
    (0, 0), # 1, 1
    (0, 1), # 1, 2
    (0, 2), # 1, 3
    (0, 3), # 1, 4
    (0, 4)  # 1, 5
]

overall_pass = True

for r, c in seats_to_test:
    passed = run_test_for_seat(r, c)
    if not passed:
        overall_pass = False
    # Small sleep between tests just in case
    time.sleep(1)

print(f"\n{CYAN}--- Final Summary ---{RESET}")
if overall_pass:
    print(f"{GREEN}ALL TESTS PASSED.{RESET}")
else:
    print(f"{RED}SOME TESTS FAILED.{RESET}")
