from flask import Blueprint, request, jsonify
from utils import decode_and_verify_access_token, extract_roles, call_data_service
import uuid
from mq_utils import publish_payment_request
from datetime import datetime
import requests

api = Blueprint('api', __name__)

# --- Auth Helper ---
def check_role(required_roles):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None, ({"ok": False, "error": "Missing Authorization header"}, 401)

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, ({"ok": False, "error": "Invalid Authorization header"}, 401)

    token = parts[1]
    try:
        decoded = decode_and_verify_access_token(token)
        user_roles = extract_roles(decoded)

        if "admin" in user_roles:
            return decoded, None

        if not required_roles:
            return decoded, None

        if any(r in user_roles for r in required_roles):
            return decoded, None

        return None, ({"ok": False, "error": "Forbidden: Insufficient rights"}, 403)

    except Exception as exc:
        return None, ({"ok": False, "error": f"Invalid token: {str(exc)}"}, 401)


def is_screening_expired(sc):
    try:
        dt_str = f"{sc.get('date')} {sc.get('time')}"
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return dt < datetime.now()
    except Exception:
        return False


@api.get("/movies")
def list_movies():
    try:
        resp = call_data_service("GET", "/movies")
        return jsonify(resp)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api.get("/movies/<mid>")
def get_movie_details(mid):
    try:
        resp = call_data_service("GET", f"/movies/{mid}")
        if not resp.get("ok"):
            return jsonify(resp), 404
        return jsonify(resp)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api.post("/movies")
def create_movie():
    user, err = check_role(["admin", "editor"])
    if err: return err

    data = request.json
    if not data or "title" not in data or "duration" not in data:
        return jsonify({"ok": False, "error": "Missing title or duration"}), 400

    try:
        resp = call_data_service("POST", "/movies", json=data)
        if resp.get("ok"):
            return jsonify(resp), 201
        return jsonify(resp), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api.put("/movies/<mid>")
def edit_movie(mid):
    user, err = check_role(["admin", "editor"])
    if err: return err

    data = request.json
    try:
        resp = call_data_service("PUT", f"/movies/{mid}", json=data)
        if not resp.get("ok"):
            return jsonify(resp), 404
        return jsonify(resp)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api.delete("/movies/<mid>")
def remove_movie(mid):
    user, err = check_role(["admin", "editor"])
    if err: return err

    try:
        resp = call_data_service("DELETE", f"/movies/{mid}")
        if not resp.get("ok"):
            return jsonify(resp), 404
        return jsonify(resp)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- ROOMS Endpoints ---

@api.get("/rooms")
def list_rooms():
    try:
        resp = call_data_service("GET", "/rooms")
        return jsonify(resp)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api.post("/rooms")
def create_room():
    user, err = check_role(["admin", "editor"])
    if err:
        return err

    data = request.json
    if not data or "number" not in data or "rows" not in data or "cols" not in data:
        return jsonify({"ok": False, "error": "Missing number, rows, or cols"}), 400

    try:
        resp = call_data_service("POST", "/rooms", json=data)
        if resp.get("ok"):
            return jsonify(resp), 201
        return jsonify(resp), resp.get("status", 400)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- SCREENINGS (Program) Endpoints ---

@api.get("/movies/<mid>/screenings")
def list_screenings(mid):
    try:
        resp = call_data_service("GET", f"/movies/{mid}/screenings")
        if not resp.get("ok"):
            return jsonify(resp), 404

        all_screenings = resp.get("data", [])
        valid_screenings = []

        for sc in all_screenings:
            if not is_screening_expired(sc):
                valid_screenings.append(sc)

        return jsonify({"ok": True, "data": valid_screenings})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api.post("/movies/<mid>/screenings")
def add_new_screening(mid):
    user, err = check_role(["admin", "editor"])
    if err: return err

    data = request.json
    if not data or "room_number" not in data or "date" not in data or "time" not in data:
        return jsonify({"ok": False, "error": "Missing room_number, date (YYYY-MM-DD), or time (HH:MM)"}), 400

    try:
        resp = call_data_service("POST", f"/movies/{mid}/screenings", json=data)
        if resp.get("ok"):
            return jsonify(resp), 201
        return jsonify(resp), resp.get("status", 400)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api.delete("/movies/<mid>/screenings/<sid>")
def remove_screening(mid, sid):
    user, err = check_role(["admin", "editor"])
    if err: return err

    try:
        resp = call_data_service("DELETE", f"/movies/{mid}/screenings/{sid}")
        if not resp.get("ok"):
            return jsonify(resp), 404
        return jsonify(resp)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- SEATS Endpoints ---

@api.get("/movies/<mid>/screenings/<sid>/seats")
def view_seats(mid, sid):
    try:
        screening_resp = call_data_service("GET", f"/screenings/{sid}")
        if not screening_resp.get("ok"):
            return jsonify({"ok": False, "error": "Screening not found"}), 404

        screening = screening_resp.get("data", {})
        if screening.get("movie_id") != mid:
            return jsonify({"ok": False, "error": "Screening does not belong to this movie"}), 404

        room_resp = call_data_service("GET", f"/rooms/{screening['room_number']}")
        if not room_resp.get("ok"):
            return jsonify({"ok": False, "error": "Room definition missing"}), 500

        room = room_resp.get("data", {})
        rows = room.get("rows", 0)
        cols = room.get("cols", 0)

        reservations_resp = call_data_service("GET", f"/reservations/screening/{sid}")
        reservations = reservations_resp.get("data", []) if reservations_resp.get("ok") else []

        taken_seats = set()
        for res in reservations:
            if res.get("status") in ['PAID', 'PENDING']:
                seat_info = res.get("seat", {})
                taken_seats.add((seat_info.get("row"), seat_info.get("col")))

        matrix = []
        for r in range(rows):
            row_arr = []
            for c in range(cols):
                if (r, c) in taken_seats:
                    row_arr.append(1)
                else:
                    row_arr.append(0)
            matrix.append(row_arr)

        return jsonify({
            "ok": True,
            "data": {
                "room": screening.get("room_number"),
                "layout": matrix,
                "rows": rows,
                "cols": cols,
                "screening": screening
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- FEED (Compatibility) ---

@api.get("/movies/feed")
def feed_compat_redirect():
    try:
        resp = call_data_service("GET", "/movies")
        return jsonify(resp)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- RESERVATIONS ---

@api.post("/reservations")
def create_reservation():
    user_payload, err = check_role(["admin", "editor", "viewer"])
    if err: return err

    user_id = user_payload.get("sub")
    if not user_id:
        return jsonify({"ok": False, "error": "Invalid token payload (no sub)"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    screening_id = data.get("screening_id")
    seat_row = data.get("seat_row")
    seat_col = data.get("seat_col")

    if not screening_id or seat_row is None or seat_col is None:
        return jsonify({"ok": False, "error": "Missing reservation fields"}), 400

    try:
        screening_resp = call_data_service("GET", f"/screenings/{screening_id}")
        if not screening_resp.get("ok"):
            return jsonify({"ok": False, "error": "Screening not found"}), 404

        screening = screening_resp.get("data", {})
        if is_screening_expired(screening):
            return jsonify({"ok": False, "error": "Screening has expired"}), 400

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    date_str = data.get("date", "")
    time_str = data.get("time", "")
    dt_obj = datetime.now()
    try:
        dt_obj = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except:
        pass

    payload = {
        "user_id": user_id,
        "movie_id": data.get("movie_id", ""),
        "room_number": data.get("room_number", ""),
        "screening_id": screening_id,
        "seat_row": seat_row,
        "seat_col": seat_col,
        "screening_datetime": dt_obj.isoformat()
    }

    try:
        res_resp = call_data_service("POST", "/reservations", json=payload)
        if not res_resp.get("ok"):
            if res_resp.get("error") and "already reserved" in res_resp.get("error", "").lower():
                return jsonify(res_resp), 409
            return jsonify(res_resp), 400

        reservation_data = res_resp.get("data", {})
        reservation_id = reservation_data.get("id")

        price = float(data.get("price", 15.0))
        amount_cents = int(price * 100)

        payment_message = {
            "reservation_id": reservation_id,
            "user_id": user_id,
            "amount": amount_cents,
            "currency": "usd"
        }

        try:
            publish_payment_request(payment_message)
        except Exception as e:
            update_resp = call_data_service("PUT", f"/reservations/{reservation_id}", json={"status": "failed"})
            return jsonify({"ok": False, "error": "Payment service unavailable"}), 503

        return jsonify({
            "ok": True,
            "message": "Reservation initiated",
            "reservation_id": reservation_id
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api.get("/reservations/me")
def get_my_reservations():
    user_id, error = check_role(["admin", "editor", "viewer"])
    if error: return error

    real_user_id = user_id.get("sub")

    try:
        resp = call_data_service("GET", f"/reservations/user/{real_user_id}")
        if not resp.get("ok"):
            return jsonify(resp), 500

        results = []
        for r in resp.get("data", []):
            try:
                movie_resp = call_data_service("GET", f"/movies/{r.get('movie_id')}")
                r["movie_title"] = movie_resp.get("data", {}).get("title", "Unknown Movie") if movie_resp.get("ok") else "Unknown Movie"
            except:
                r["movie_title"] = "Unknown Movie"
            results.append(r)

        return jsonify({"ok": True, "data": results})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

