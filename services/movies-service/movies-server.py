
import os
from flask import Flask
from dotenv import load_dotenv
from utils import wait_for_keycloak
from models import db
from routes import api
from mq_utils import start_payment_result_listener
from utils import DATABASE_URL, PORT

load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

db.init_app(app)

app.register_blueprint(api)

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    wait_for_keycloak()

    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"DB creation error : {e}")

    # Start RabbitMQ Listener
    start_payment_result_listener(app)

    app.run(host="0.0.0.0", port=int(PORT), debug=True)


