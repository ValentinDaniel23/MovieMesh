
import os
from flask import Flask
from dotenv import load_dotenv
from utils import wait_for_keycloak, wait_for_rabbitmq, PORT
from routes import api
from mq_utils import start_payment_result_listener

load_dotenv()

app = Flask(__name__)

app.register_blueprint(api)

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    wait_for_keycloak()
    wait_for_rabbitmq()

    # Start RabbitMQ Listener
    start_payment_result_listener()

    app.run(host="0.0.0.0", port=int(PORT), debug=False)
