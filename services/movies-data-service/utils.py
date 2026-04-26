import os
import time
import requests

def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value

DATABASE_URL = _get_env("DATABASE_URL")
REDIS_HOST = _get_env("REDIS_HOST")
REDIS_PORT = int(_get_env("REDIS_PORT"))
PORT = _get_env("PORT")

def wait_for_dependencies():
    wait_for_redis()
    wait_for_database()

def wait_for_redis():
    for _ in range(60):
        try:
            import redis
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=2)
            r.ping()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Redis not ready after 60 seconds")

def wait_for_database():
    from sqlalchemy import create_engine, text
    for _ in range(60):
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Database not ready after 60 seconds")
