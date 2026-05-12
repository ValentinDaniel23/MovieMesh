import os
import json
from flask import Flask, request, jsonify
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from models import db, Movie, Room, Screening, Reservation
from db_utils import (
    init_db, seed_initial_data, get_movie_by_id, get_all_movies,
    get_room_by_number, get_all_rooms, get_screening_by_id, 
    get_screenings_by_movie, get_reservation_by_id, get_all_reservations,
    get_seat_reservation, create_movie, update_movie, delete_movie,
    create_room, delete_room, create_screening, delete_screening,
    create_reservation, update_reservation_status, delete_reservation
)
from cache_utils import (
    add_movie as cache_add_movie, delete_movie as cache_delete_movie,
    add_room as cache_add_room, delete_room as cache_delete_room,
    add_screening as cache_add_screening, delete_screening as cache_delete_screening,
    invalidate_movies, invalidate_rooms, invalidate_screenings
)
from utils import wait_for_dependencies, PORT

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

init_db(app)

def response(ok, data=None, error=None, status=200):
    status_code = 200 if ok else 400
    if error and status > 0:
        status_code = status
    return jsonify({"ok": ok, "data": data, "error": error}), status_code

@app.route("/health", methods=["GET"])
def health():
    return response(True, {"status": "healthy"})

# Movies endpoints
@app.route("/movies", methods=["GET"])
def get_movies():
    try:
        movies = get_all_movies()
        data = [m.to_dict() for m in movies]
        return response(True, data)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/movies", methods=["POST"])
def create_movie_endpoint():
    try:
        payload = request.get_json()
        if not payload or not payload.get("title"):
            return response(False, error="Missing title", status=400)
        
        title = payload["title"]
        description = payload.get("description")
        duration = payload.get("duration")
        
        if not duration:
            return response(False, error="Missing duration", status=400)
        
        movie = create_movie(title, description, duration)
        invalidate_movies()
        cache_add_movie(movie.to_dict())
        return response(True, movie.to_dict(), status=201)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/movies/<movie_id>", methods=["GET"])
def get_movie(movie_id):
    try:
        movie = get_movie_by_id(movie_id)
        if not movie:
            return response(False, error="Movie not found", status=404)
        return response(True, movie.to_dict())
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/movies/<movie_id>", methods=["PUT"])
def update_movie_endpoint(movie_id):
    try:
        movie = get_movie_by_id(movie_id)
        if not movie:
            return response(False, error="Movie not found", status=404)
        
        payload = request.get_json()
        title = payload.get("title")
        description = payload.get("description")
        duration = payload.get("duration")
        
        movie = update_movie(movie_id, title, description, duration)
        invalidate_movies()
        cache_add_movie(movie.to_dict())
        return response(True, movie.to_dict())
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/movies/<movie_id>", methods=["DELETE"])
def delete_movie_endpoint(movie_id):
    try:
        movie = get_movie_by_id(movie_id)
        if not movie:
            return response(False, error="Movie not found", status=404)
        
        delete_movie(movie_id)
        invalidate_movies()
        cache_delete_movie(movie_id)
        return response(True, {"id": movie_id})
    except Exception as e:
        return response(False, error=str(e), status=500)

# Rooms endpoints
@app.route("/rooms", methods=["GET"])
def get_rooms():
    try:
        rooms = get_all_rooms()
        data = [r.to_dict() for r in rooms]
        return response(True, data)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/rooms", methods=["POST"])
def create_room_endpoint():
    try:
        payload = request.get_json()
        if not payload or not payload.get("number"):
            return response(False, error="Missing number", status=400)
        
        number = payload["number"]
        rows = payload.get("rows")
        cols = payload.get("cols")
        
        if not rows or not cols:
            return response(False, error="Missing rows or cols", status=400)
        
        existing = get_room_by_number(number)
        if existing:
            return response(False, error="Room already exists", status=409)
        
        room = create_room(number, rows, cols)
        invalidate_rooms()
        cache_add_room(number, rows, cols)
        return response(True, room.to_dict(), status=201)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/rooms/<number>", methods=["GET"])
def get_room(number):
    try:
        room = get_room_by_number(number)
        if not room:
            return response(False, error="Room not found", status=404)
        return response(True, room.to_dict())
    except Exception as e:
        return response(False, error=str(e), status=500)

# Screenings endpoints
@app.route("/movies/<movie_id>/screenings", methods=["GET"])
def get_movie_screenings(movie_id):
    try:
        movie = get_movie_by_id(movie_id)
        if not movie:
            return response(False, error="Movie not found", status=404)
        
        screenings = get_screenings_by_movie(movie_id)
        data = [s.to_dict() for s in screenings]
        return response(True, data)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/movies/<movie_id>/screenings", methods=["POST"])
def create_screening_endpoint(movie_id):
    try:
        movie = get_movie_by_id(movie_id)
        if not movie:
            return response(False, error="Movie not found", status=404)
        
        payload = request.get_json()
        room_number = payload.get("room_number")
        date = payload.get("date")
        time = payload.get("time")
        
        if not room_number or not date or not time:
            return response(False, error="Missing required fields", status=400)
        
        room = get_room_by_number(room_number)
        if not room:
            return response(False, error="Room not found", status=404)
        
        screening = create_screening(movie_id, room_number, date, time)
        invalidate_screenings()
        cache_add_screening(screening.to_dict())
        return response(True, screening.to_dict(), status=201)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/screenings/<screening_id>", methods=["GET"])
def get_screening(screening_id):
    try:
        screening = get_screening_by_id(screening_id)
        if not screening:
            return response(False, error="Screening not found", status=404)
        return response(True, screening.to_dict())
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/movies/<movie_id>/screenings/<screening_id>", methods=["DELETE"])
def delete_screening_endpoint(movie_id, screening_id):
    try:
        screening = get_screening_by_id(screening_id)
        if not screening:
            return response(False, error="Screening not found", status=404)
        if screening.movie_id != movie_id:
            return response(False, error="Screening does not belong to this movie", status=400)

        delete_screening(screening_id)
        invalidate_screenings()
        cache_delete_screening(screening_id)
        return response(True, {"id": screening_id})
    except Exception as e:
        return response(False, error=str(e), status=500)

# Reservations endpoints
@app.route("/reservations", methods=["GET"])
def get_reservations():
    try:
        reservations = get_all_reservations()
        data = [r.to_dict() for r in reservations]
        return response(True, data)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/reservations/user/<user_id>", methods=["GET"])
def get_reservations_by_user(user_id):
    try:
        reservations = Reservation.query.filter_by(user_id=user_id).order_by(Reservation.created_at.desc()).all()
        data = [r.to_dict() for r in reservations]
        return response(True, data)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/reservations/screening/<screening_id>", methods=["GET"])
def get_reservations_by_screening(screening_id):
    try:
        reservations = Reservation.query.filter_by(screening_id=screening_id).all()
        data = [r.to_dict() for r in reservations]
        return response(True, data)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/reservations", methods=["POST"])
def create_reservation_endpoint():
    try:
        payload = request.get_json()
        user_id = payload.get("user_id")
        movie_id = payload.get("movie_id")
        room_number = payload.get("room_number")
        screening_id = payload.get("screening_id")
        seat_row = payload.get("seat_row")
        seat_col = payload.get("seat_col")
        screening_datetime_str = payload.get("screening_datetime")
        
        if not all([user_id, movie_id, room_number, screening_id, seat_row is not None, seat_col is not None, screening_datetime_str]):
            return response(False, error="Missing required fields", status=400)
        
        screening = get_screening_by_id(screening_id)
        if not screening:
            return response(False, error="Screening not found", status=404)
        
        existing = get_seat_reservation(screening_id, seat_row, seat_col)
        if existing:
            return response(False, error="Seat already reserved", status=409)
        
        screening_datetime = datetime.fromisoformat(screening_datetime_str)
        reservation = create_reservation(user_id, movie_id, room_number, screening_id, seat_row, seat_col, screening_datetime)
        
        if not reservation:
            return response(False, error="Failed to create reservation", status=400)
        
        return response(True, reservation.to_dict(), status=201)
    except ValueError as e:
        return response(False, error="Invalid datetime format", status=400)
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/reservations/<reservation_id>", methods=["GET"])
def get_reservation(reservation_id):
    try:
        reservation = get_reservation_by_id(reservation_id)
        if not reservation:
            return response(False, error="Reservation not found", status=404)
        return response(True, reservation.to_dict())
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/reservations/<reservation_id>", methods=["PUT"])
def update_reservation_endpoint(reservation_id):
    try:
        reservation = get_reservation_by_id(reservation_id)
        if not reservation:
            return response(False, error="Reservation not found", status=404)
        
        payload = request.get_json()
        status = payload.get("status")
        
        if not status:
            return response(False, error="Missing status", status=400)
        
        reservation = update_reservation_status(reservation_id, status)
        return response(True, reservation.to_dict())
    except Exception as e:
        return response(False, error=str(e), status=500)

@app.route("/reservations/<reservation_id>", methods=["DELETE"])
def delete_reservation_endpoint(reservation_id):
    try:
        reservation = get_reservation_by_id(reservation_id)
        if not reservation:
            return response(False, error="Reservation not found", status=404)
        
        delete_reservation(reservation_id)
        return response(True, {"id": reservation_id})
    except Exception as e:
        return response(False, error=str(e), status=500)

if __name__ == "__main__":
    wait_for_dependencies()
    seed_initial_data(app)
    app.run(host="0.0.0.0", port=int(PORT), debug=False)
