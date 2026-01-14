from flask import Blueprint, request, jsonify
from utils import decode_and_verify_access_token, extract_roles
import uuid
from models import db, Movie, Room, Screening
from redis_client import (
    add_room as redis_add_room, get_room, get_all_rooms, add_movie as redis_add_movie,
    get_movie, get_all_movies, update_movie as redis_update_movie, delete_movie as redis_delete_movie,
    add_screening as redis_add_screening, get_screening, get_screenings_for_movie, delete_screening as redis_delete_screening
)
from models import db, Movie, Room, Screening, Reservation
from mq_utils import publish_payment_request
from datetime import datetime

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


# --- MOVIES Endpoints ---

@api.get("/movies")
def list_movies():
    movies = get_all_movies()
    return jsonify({"ok": True, "data": movies})

@api.get("/movies/<mid>")
def get_movie_details(mid):
    movie = get_movie(mid)
    if not movie:
        return jsonify({"ok": False, "error": "Movie not found"}), 404
    return jsonify({"ok": True, "data": movie})

@api.post("/movies")
def create_movie():
    user, err = check_role(["admin", "editor"])
    if err: return err

    data = request.json
    if not data or "title" not in data or "duration" not in data:
        return jsonify({"ok": False, "error": "Missing title or duration"}), 400

    new_movie = Movie(
        title=data["title"],
        description=data.get("description", ""),
        duration=data["duration"]
    )

    try:
        db.session.add(new_movie)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"DB Error: {str(e)}"}), 500

    movie_dict = {
        "id": new_movie.id,
        "title": new_movie.title,
        "description": new_movie.description,
        "duration": new_movie.duration
    }

    redis_add_movie(movie_dict)
    return jsonify({"ok": True, "message": "Movie created", "data": movie_dict}), 201

@api.put("/movies/<mid>")
def edit_movie(mid):
    user, err = check_role(["admin", "editor"])
    if err: return err

    data = request.json

    movie = db.session.get(Movie, mid)
    if movie:
        try:
            if "title" in data: movie.title = data["title"]
            if "description" in data: movie.description = data["description"]
            if "duration" in data: movie.duration = data["duration"]
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": f"DB Error: {str(e)}"}), 500

    updated = redis_update_movie(mid, data)
    if not updated:
        return jsonify({"ok": False, "error": "Movie not found"}), 404
    return jsonify({"ok": True, "message": "Movie updated", "data": updated})

@api.delete("/movies/<mid>")
def remove_movie(mid):
    user, err = check_role(["admin", "editor"])
    if err: return err

    redis_delete_movie(mid)
    return jsonify({"ok": True, "message": "Movie deleted (from active cache)"})


# --- ROOMS Endpoints ---

@api.get("/rooms")
def list_rooms():
    rooms = get_all_rooms()
    return jsonify({"ok": True, "data": rooms})

@api.post("/rooms")
def create_room():
    user, err = check_role(["admin", "editor"])
    if err:
        return err

    data = request.json
    if not data or "number" not in data or "rows" not in data or "cols" not in data:
         return jsonify({"ok": False, "error": "Missing number, rows, or cols"}), 400

    if get_room(data["number"]):
        return jsonify({"ok": False, "error": "Room already exists"}), 409

    new_room = Room(
        number=data["number"],
        rows=int(data["rows"]),
        cols=int(data["cols"])
    )
    try:
        db.session.add(new_room)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"DB Error: {str(e)}"}), 500

    redis_add_room(data["number"], int(data["rows"]), int(data["cols"]))
    return jsonify({"ok": True, "message": "Room created"}), 201


# --- SCREENINGS (Program) Endpoints ---

@api.get("/movies/<mid>/screenings")
def list_screenings(mid):
    if not get_movie(mid):
        return jsonify({"ok": False, "error": "Movie not found"}), 404

    all_screenings = get_screenings_for_movie(mid)
    valid_screenings = []

    for sc in all_screenings:
        if is_screening_expired(sc):
            print(f"Expired screening {sc['id']} detected. Removing from Redis.")
            redis_delete_screening(sc['id'])
        else:
            valid_screenings.append(sc)

    return jsonify({"ok": True, "data": valid_screenings})

@api.post("/movies/<mid>/screenings")
def add_new_screening(mid):
    user, err = check_role(["admin", "editor"])
    if err: return err

    if not get_movie(mid):
        return jsonify({"ok": False, "error": "Movie not found"}), 404

    data = request.json

    if not data or "room_number" not in data or "date" not in data or "time" not in data:
        return jsonify({"ok": False, "error": "Missing room_number, date (YYYY-MM-DD), or time (HH:MM)"}), 400

    room_num = data["room_number"]
    if not get_room(room_num):
         return jsonify({"ok": False, "error": f"Room {room_num} does not exist"}), 400

    new_screening = Screening(
        movie_id=mid,
        room_number=room_num,
        date=data["date"],
        time=data["time"]
    )

    try:
        db.session.add(new_screening)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"DB Error: {str(e)}"}), 500

    screening_dict = {
        "id": new_screening.id,
        "movie_id": mid,
        "room_number": room_num,
        "date": data["date"],
        "time": data["time"]
    }

    redis_add_screening(screening_dict)
    return jsonify({"ok": True, "message": "Screening added", "data": screening_dict}), 201

@api.delete("/movies/<mid>/screenings/<sid>")
def remove_screening(mid, sid):
    user, err = check_role(["admin", "editor"])
    if err: return err

    success = redis_delete_screening(sid)
    if not success:
        return jsonify({"ok": False, "error": "Screening not found (in redis)"}), 404
    return jsonify({"ok": True, "message": "Screening deleted (from active cache)"})


# --- SEATS Endpoints ---

@api.get("/movies/<mid>/screenings/<sid>/seats")
def view_seats(mid, sid):
    screening = get_screening(sid)
    if not screening:
        return jsonify({"ok": False, "error": "Screening not found"}), 404

    room_num = screening["room_number"]
    room = get_room(room_num)
    if not room:
         return jsonify({"ok": False, "error": "Room definition missing"}), 500

    rows = room["rows"]
    cols = room["cols"]

    # Construct Matrix
    # 0 = Free, 1 = Taken (Reserved/Paid)

    matrix = []

    # Pre-fetch reservations for this screening
    taken_seats = set()
    try:
        reservations = Reservation.query.filter(
            Reservation.screening_id == sid,
            Reservation.status.in_(['paid', 'pending', 'PAID', 'PENDING'])
        ).all()
        for res in reservations:
            taken_seats.add((res.seat_row, res.seat_column))
    except Exception as e:
        print(f"Error fetching reservations: {e}")

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
            "room": room_num,
            "layout": matrix,
            "rows": rows,
            "cols": cols,
            "screening": screening
        }
    })


# --- FEED (Compatibility) ---

@api.get("/movies/feed")
def feed_compat_redirect():
    movies = get_all_movies()
    return jsonify({"ok": True, "data": movies})


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

    screening = get_screening(screening_id)
    if not screening:
        return jsonify({"ok": False, "error": "Screening not found"}), 404

    if is_screening_expired(screening):
        redis_delete_screening(screening_id)
        return jsonify({"ok": False, "error": "Screening has expired"}), 400


    try:
        existing = Reservation.query.filter_by(
            screening_id=screening_id,
            seat_row=seat_row,
            seat_column=seat_col
        ).filter(Reservation.status.in_(['paid', 'pending'])).first()

        if existing:
            return jsonify({"ok": False, "error": "Seat already reserved"}), 409

    except Exception as e:
        return jsonify({"ok": False, "error": "System busy"}), 500

    try:
        date_str = screening.get("date")
        time_str = screening.get("time")
        dt_obj = datetime.now()
        try:
            dt_obj = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except:
            pass

        new_res = Reservation(
            user_id=user_id,
            movie_id=screening.get("movie_id", "unknown"),
            room_number=screening.get("room_number", "unknown"),
            screening_id=screening_id,
            seat_row=seat_row,
            seat_column=seat_col,
            screening_datetime=dt_obj,
            status="pending"
        )
        db.session.add(new_res)
        db.session.commit()

        reservation_id = new_res.id
    except Exception as e:
        db.session.rollback()
        if "ix_unique_seat_reservation" in str(e) or "UniqueViolation" in str(e):
             return jsonify({"ok": False, "error": "Seat already reserved"}), 409

        return jsonify({"ok": False, "error": "Could not create reservation record"}), 500

    # Payload for RabbitMQ (payment_worker)

    price = float(screening.get("price", 15.0))
    amount_cents = int(price * 100)

    payment_message = {
        "reservation_id": reservation_id,
        "user_id": user_id,
        "amount": amount_cents,
        "currency": "usd"
    }

    # Publish
    try:
        publish_payment_request(payment_message)
    except Exception as e:
        new_res.status = "failed"
        db.session.commit()
        return jsonify({"ok": False, "error": "Payment service unavailable"}), 503

    return jsonify({
        "ok": True,
        "message": "Reservation initiated",
        "reservation_id": reservation_id
    }), 200

@api.get("/reservations/me")
def get_my_reservations():
    user_id, error = check_role(["admin", "editor", "viewer"])
    if error: return error

    real_user_id = user_id.get("sub")

    reservations = Reservation.query.filter_by(user_id=real_user_id).order_by(Reservation.created_at.desc()).all()

    results = []
    for r in reservations:
        movie = get_movie(r.movie_id)
        movie_title = movie.get("title", "Unknown Movie") if movie else "Unknown Movie"

        rd = r.to_dict()
        rd["movie_title"] = movie_title
        results.append(rd)

    return jsonify({"ok": True, "data": results})

