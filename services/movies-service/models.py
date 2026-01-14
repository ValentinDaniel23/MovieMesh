from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, text
import uuid
from typing import Optional
from datetime import datetime

db = SQLAlchemy()

class Movie(db.Model):
    __tablename__ = 'movies'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False) # Minutes
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "duration": self.duration
        }

class Room(db.Model):
    __tablename__ = 'rooms'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    cols: Mapped[int] = mapped_column(Integer, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "number": self.number,
            "rows": self.rows,
            "cols": self.cols
        }

class Screening(db.Model):
    __tablename__ = 'screenings'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    movie_id: Mapped[str] = mapped_column(ForeignKey('movies.id'), nullable=False)
    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    time: Mapped[str] = mapped_column(String(10), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "movie_id": self.movie_id,
            "room_number": self.room_number,
            "date": self.date,
            "time": self.time
        }

class Reservation(db.Model):
    __tablename__ = 'reservations'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(255), nullable=False) # Keycloak Subject ID
    movie_id: Mapped[str] = mapped_column(String(36), nullable=False)
    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    screening_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seat_row: Mapped[int] = mapped_column(Integer, nullable=False)
    seat_column: Mapped[int] = mapped_column(Integer, nullable=False)
    screening_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            'ix_unique_seat_reservation',
            'screening_id', 'seat_row', 'seat_column',
            unique=True,
            postgresql_where=text("status IN ('paid', 'pending', 'PAID', 'PENDING')")
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "movie_id": self.movie_id,
            "screening_id": self.screening_id,
            "room_number": self.room_number,
            "seat": {"row": self.seat_row, "col": self.seat_column},
            "status": self.status,
            "screening_datetime": self.screening_datetime.isoformat()
        }
