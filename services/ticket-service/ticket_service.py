import os
import json
import time
import threading
import pika
import qrcode
from flask import Flask, send_from_directory
from reportlab.pdfgen import canvas

app = Flask(__name__)

def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value

RABBITMQ_HOST = _get_env("RABBITMQ_HOST")
MQ_EXCHANGE_EVENTS = _get_env("MQ_EXCHANGE_EVENTS")
TICKETS_DIR = "/app/tickets"

if not os.path.exists(TICKETS_DIR):
    os.makedirs(TICKETS_DIR)

def generate_ticket(data):
    if data.get("status") != "PAID":
        return

    res_id = data.get("reservation_id")
    filename = f"ticket_{res_id}.pdf"
    filepath = os.path.join(TICKETS_DIR, filename)

    print(f" [Ticket] Generating PDF for {res_id}...")

    c = canvas.Canvas(filepath)
    c.drawString(100, 800, "CINEMA TICKET")
    c.drawString(100, 780, f"Reservation ID: {res_id}")
    c.drawString(100, 760, f"User ID: {data.get('user_id')}")
    c.drawString(100, 740, "Status: PAID")

    qr_path = os.path.join(TICKETS_DIR, f"qr_{res_id}.png")
    qr = qrcode.make(res_id)
    qr.save(qr_path)

    c.drawImage(qr_path, 100, 500, width=100, height=100)
    c.save()

    if os.path.exists(qr_path):
        os.remove(qr_path)

    print(f" [Ticket] Saved: {filepath}")

def rabbit_listener():
    print(f" [Ticket] Connecting to {RABBITMQ_HOST}...")
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()

            channel.exchange_declare(exchange=MQ_EXCHANGE_EVENTS, exchange_type='fanout')
            queue_name = 'q_tickets_generation'
            channel.queue_declare(queue=queue_name, durable=True)
            channel.queue_bind(exchange=MQ_EXCHANGE_EVENTS, queue=queue_name)

            def callback(ch, method, properties, body):
                try:
                    data = json.loads(body)
                    generate_ticket(data)
                except Exception as ex:
                    print(f" [Ticket] Process error: {ex}")
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            print(" [Ticket] Listening...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print(" [Ticket] Connection failed, retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f" [Ticket] Error: {e}, retrying in 5s...")
            time.sleep(5)

threading.Thread(target=rabbit_listener, daemon=True).start()

@app.route("/tickets/<filename>")
def get_ticket(filename):
    return send_from_directory(TICKETS_DIR, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
