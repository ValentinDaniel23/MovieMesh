import os
import json
import redis
from utils import REDIS_HOST, REDIS_PORT

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

PREFIX_ROOM = "room"
PREFIX_MOVIE = "movie"
PREFIX_SCREENING = "screening"
SET_ROOMS = "rooms" # Set of room IDs
SET_MOVIES = "movies" # Set of movie IDs
SET_SCREENINGS_BY_MOVIE = "movie_screenings" # key: movie_screenings:{movie_id} -> Set of screening IDs

# --- Rooms ---
def add_room(number, rows, cols):
    key = f"{PREFIX_ROOM}:{number}"
    data = {"number": number, "rows": rows, "cols": cols}

    r.set(key, json.dumps(data))
    r.sadd(SET_ROOMS, number)
    return data

def get_room(number):
    key = f"{PREFIX_ROOM}:{number}"
    data = r.get(key)
    return json.loads(data) if data else None

def delete_room(number):
    mids = r.smembers(SET_MOVIES)
    for mid in mids:
        sids = r.smembers(f"{SET_SCREENINGS_BY_MOVIE}:{mid}")
        for sid in sids:
            sc = get_screening(sid)
            if sc and sc.get("room_number") == number:
                delete_screening(sid)

    key = f"{PREFIX_ROOM}:{number}"
    r.delete(key)
    r.srem(SET_ROOMS, number)

def get_all_rooms():
    numbers = r.smembers(SET_ROOMS)
    rooms = []
    for num in numbers:
        room = get_room(num)
        if room:
            rooms.append(room)
    return rooms

# --- Movies ---
def add_movie(movie_curr):
    # movie_curr is a dict
    mid = movie_curr["id"]
    key = f"{PREFIX_MOVIE}:{mid}"
    r.set(key, json.dumps(movie_curr))
    r.sadd(SET_MOVIES, mid)
    return movie_curr

def get_movie(mid):
    key = f"{PREFIX_MOVIE}:{mid}"
    data = r.get(key)
    return json.loads(data) if data else None

def get_all_movies():
    mids = r.smembers(SET_MOVIES)
    movies = []
    for mid in mids:
        mv = get_movie(mid)
        if mv:
            movies.append(mv)
    return movies

def update_movie(mid, data):
    current = get_movie(mid)
    if not current:
        return None
    current.update(data)
    add_movie(current)
    return current

def delete_movie(mid):
    screenings = get_screenings_for_movie(mid)
    for sc in screenings:
        delete_screening(sc["id"])

    key = f"{PREFIX_MOVIE}:{mid}"
    r.delete(key)
    r.srem(SET_MOVIES, mid)

# --- Screenings ---
def add_screening(screening_data):
    sid = screening_data["id"]
    mid = screening_data["movie_id"]
    key = f"{PREFIX_SCREENING}:{sid}"

    r.set(key, json.dumps(screening_data))
    r.sadd(f"{SET_SCREENINGS_BY_MOVIE}:{mid}", sid)
    return screening_data

def get_screening(sid):
    key = f"{PREFIX_SCREENING}:{sid}"
    data = r.get(key)
    return json.loads(data) if data else None

def get_screenings_for_movie(mid):
    sids = r.smembers(f"{SET_SCREENINGS_BY_MOVIE}:{mid}")
    screenings = []
    for sid in sids:
        sc = get_screening(sid)
        if sc:
            screenings.append(sc)

    try:
        screenings.sort(key=lambda x: (x["date"], x["time"]))
    except:
        pass
    return screenings

def delete_screening(sid):
    sc = get_screening(sid)
    if sc:
        mid = sc["movie_id"]
        r.srem(f"{SET_SCREENINGS_BY_MOVIE}:{mid}", sid)
        r.delete(f"{PREFIX_SCREENING}:{sid}")
        return True
    return False
