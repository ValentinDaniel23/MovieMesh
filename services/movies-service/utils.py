import os
import time
from typing import Any
import jwt
import requests

def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value

# Configuration
KEYCLOAK_INTERNAL = _get_env("KEYCLOAK_URL_INTERNAL").rstrip("/")
REALM = _get_env("KEYCLOAK_REALM")
CLIENT_ID = _get_env("KEYCLOAK_CLIENT_ID")

RABBITMQ_HOST = _get_env("RABBITMQ_HOST")
PORT = _get_env("PORT")

# Data service URL
MOVIES_DATA_SERVICE_URL = _get_env("MOVIES_DATA_SERVICE_URL").rstrip("/")

JWKS_URL = f"{KEYCLOAK_INTERNAL}/realms/{REALM}/protocol/openid-connect/certs"

_jwks_cache: dict[str, Any] | None = None
_jwks_cache_expires_at: float = 0.0

def wait_for_rabbitmq():
    import pika
    for _ in range(120):
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, socket_timeout=2))
            conn.close()
            print(f" [MQ] RabbitMQ at {RABBITMQ_HOST} is ready")
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("RabbitMQ not ready after 240 seconds")

def wait_for_keycloak():
    url = f"{KEYCLOAK_INTERNAL}/health/ready"

    # Increase timeout to 5 minutes (150 * 2s)
    for _ in range(150):
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Keycloak not ready after 300 seconds")

def _fetch_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_cache_expires_at

    now = time.time()
    if _jwks_cache and now < _jwks_cache_expires_at:
        return _jwks_cache

    resp = requests.get(JWKS_URL, timeout=10)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_cache_expires_at = now + 60
    return _jwks_cache

def decode_and_verify_access_token(access_token: str) -> dict[str, Any]:
    jwks = _fetch_jwks()
    unverified_header = jwt.get_unverified_header(access_token)
    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("JWT missing kid")

    key = None
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
            break
    if key is None:
        raise ValueError("No matching JWK for kid")

    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": False,
    }

    kwargs: dict[str, Any] = {
        "key": key,
        "algorithms": ["RS256"],
        "options": options,
    }

    return jwt.decode(access_token, **kwargs)

def extract_roles(decoded_token: dict[str, Any]) -> set[str]:
    resource_access = decoded_token.get("resource_access") or {}
    client_roles = (resource_access.get(CLIENT_ID) or {}).get("roles") or []

    realm_access = decoded_token.get("realm_access") or {}
    realm_roles = realm_access.get("roles") or []

    return set(client_roles).union(set(realm_roles))

def call_data_service(method: str, endpoint: str, **kwargs) -> dict[str, Any]:
    """
    Call movies-data-service API and return the JSON response.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint path (e.g., "/movies", "/movies/<id>")
        **kwargs: Additional arguments to pass to requests (e.g., json, params, headers)
    
    Returns:
        JSON response as dictionary
    """
    url = f"{MOVIES_DATA_SERVICE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10, **kwargs)
        elif method == "POST":
            response = requests.post(url, timeout=10, **kwargs)
        elif method == "PUT":
            response = requests.put(url, timeout=10, **kwargs)
        elif method == "DELETE":
            response = requests.delete(url, timeout=10, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        try:
            return response.json()
        except Exception:
            response.raise_for_status()
            return {"ok": False, "error": f"Non-JSON response: {response.text[:200]}"}
    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "error": f"Data service request failed: {str(e)}",
            "status": getattr(e.response, "status_code", 500) if hasattr(e, "response") else 500
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Unexpected error: {str(e)}",
            "status": 500
        }
