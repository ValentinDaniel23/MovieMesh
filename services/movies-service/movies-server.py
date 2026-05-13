
import os
from flask import Flask, Response
from dotenv import load_dotenv
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from utils import wait_for_keycloak, wait_for_rabbitmq, PORT
from routes import api
from mq_utils import start_payment_result_listener

load_dotenv()

app = Flask(__name__)

app.register_blueprint(api)

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    wait_for_keycloak()
    wait_for_rabbitmq()

    # Start RabbitMQ Listener
    start_payment_result_listener()

    app.run(host="0.0.0.0", port=int(PORT), debug=False)
