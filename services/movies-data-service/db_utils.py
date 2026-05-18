from models import db, Movie, Room, Screening, Reservation
from datetime import datetime
import uuid

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()

def seed_initial_data(app):
    with app.app_context():
        if Movie.query.first() is not None:
            return
        
        movies = [
            Movie(title="The Matrix", description="A hacker discovers reality", duration=136),
            Movie(title="Inception", description="A mind-bending thriller", duration=148),
            Movie(title="Interstellar", description="A journey through space", duration=169),
        ]
        
        for movie in movies:
            db.session.add(movie)
        db.session.commit()
        
        rooms = [
            Room(number="A1", rows=10, cols=15),
            Room(number="A2", rows=8, cols=12),
            Room(number="B1", rows=12, cols=18),
        ]
        
        for room in rooms:
            db.session.add(room)
        db.session.commit()
        
        screenings = [
            Screening(movie_id=movies[0].id, room_number="A1", date="2026-06-10", time="18:00"),
            Screening(movie_id=movies[0].id, room_number="A2", date="2026-06-10", time="20:00"),
            Screening(movie_id=movies[1].id, room_number="B1", date="2026-06-11", time="19:00"),
        ]
        
        for screening in screenings:
            db.session.add(screening)
        db.session.commit()

def get_movie_by_id(movie_id):
    return Movie.query.get(movie_id)

def get_all_movies():
    return Movie.query.all()

def get_room_by_number(number):
    return Room.query.filter_by(number=number).first()

def get_all_rooms():
    return Room.query.all()

def get_screening_by_id(screening_id):
    return Screening.query.get(screening_id)

def get_screenings_by_movie(movie_id):
    return Screening.query.filter_by(movie_id=movie_id).all()

def get_reservation_by_id(reservation_id):
    return Reservation.query.get(reservation_id)

def get_all_reservations():
    return Reservation.query.all()

def get_seat_reservation(screening_id, row, col, valid_statuses=None):
    if valid_statuses is None:
        valid_statuses = ["PENDING", "PAID"]
    return Reservation.query.filter(
        Reservation.screening_id == screening_id,
        Reservation.seat_row == row,
        Reservation.seat_column == col,
        Reservation.status.in_(valid_statuses)
    ).first()

def create_movie(title, description, duration):
    movie = Movie(title=title, description=description, duration=duration)
    db.session.add(movie)
    db.session.commit()
    return movie

def update_movie(movie_id, title=None, description=None, duration=None):
    movie = Movie.query.get(movie_id)
    if not movie:
        return None
    if title:
        movie.title = title
    if description:
        movie.description = description
    if duration:
        movie.duration = duration
    db.session.commit()
    return movie

def delete_movie(movie_id):
    movie = Movie.query.get(movie_id)
    if movie:
        Screening.query.filter_by(movie_id=movie_id).delete()
        db.session.delete(movie)
        db.session.commit()
        return True
    return False

def create_room(number, rows, cols):
    existing = Room.query.filter_by(number=number).first()
    if existing:
        return None
    room = Room(number=number, rows=rows, cols=cols)
    db.session.add(room)
    db.session.commit()
    return room

def delete_room(number):
    room = Room.query.filter_by(number=number).first()
    if room:
        Screening.query.filter_by(room_number=number).delete()
        db.session.delete(room)
        db.session.commit()
        return True
    return False

def create_screening(movie_id, room_number, date, time):
    movie = Movie.query.get(movie_id)
    if not movie:
        return None
    room = Room.query.filter_by(number=room_number).first()
    if not room:
        return None
    screening = Screening(movie_id=movie_id, room_number=room_number, date=date, time=time)
    db.session.add(screening)
    db.session.commit()
    return screening

def delete_screening(screening_id):
    screening = Screening.query.get(screening_id)
    if screening:
        Reservation.query.filter_by(screening_id=screening_id).delete()
        db.session.delete(screening)
        db.session.commit()
        return True
    return False

def create_reservation(user_id, movie_id, room_number, screening_id, seat_row, seat_col, screening_datetime):
    existing = get_seat_reservation(screening_id, seat_row, seat_col)
    if existing:
        return None
    reservation = Reservation(
        user_id=user_id,
        movie_id=movie_id,
        room_number=room_number,
        screening_id=screening_id,
        seat_row=seat_row,
        seat_column=seat_col,
        screening_datetime=screening_datetime,
        status="PENDING"
    )
    db.session.add(reservation)
    db.session.commit()
    return reservation

def update_reservation_status(reservation_id, status):
    reservation = Reservation.query.get(reservation_id)
    if reservation:
        reservation.status = status
        db.session.commit()
        return reservation
    return None

def delete_reservation(reservation_id):
    reservation = Reservation.query.get(reservation_id)
    if reservation:
        db.session.delete(reservation)
        db.session.commit()
        return True
    return False
