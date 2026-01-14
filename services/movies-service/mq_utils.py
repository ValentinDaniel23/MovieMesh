import os
import json
import pika
import time
import threading
from models import db, Reservation
from flask import Flask

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
MQ_QUEUE_REQUESTS = os.getenv("MQ_QUEUE_REQUESTS", "payment_requests")
MQ_EXCHANGE_EVENTS = os.getenv("MQ_EXCHANGE_EVENTS", "payment_events")

def get_connection():
    return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))

def publish_payment_request(payload):
    try:
        connection = get_connection()
        channel = connection.channel()
        channel.queue_declare(queue=MQ_QUEUE_REQUESTS, durable=True)

        channel.basic_publish(
            exchange='',
            routing_key=MQ_QUEUE_REQUESTS,
            body=json.dumps(payload),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        print(f" [MQ] Request sent for Reservation {payload.get('reservation_id')}")
    except Exception as e:
        print(f" [MQ] Publish error: {e}")

def start_payment_result_listener(app: Flask):
    def listener():
        print(f" [MQ] Listener connecting to {RABBITMQ_HOST}...")
        while True:
            try:
                connection = get_connection()
                channel = connection.channel()

                channel.exchange_declare(exchange=MQ_EXCHANGE_EVENTS, exchange_type='fanout')
                queue_name = 'q_movies_payment_updates'
                channel.queue_declare(queue=queue_name, durable=True)
                channel.queue_bind(exchange=MQ_EXCHANGE_EVENTS, queue=queue_name)

                def callback(ch, method, properties, body):
                    data = json.loads(body)
                    res_id = data.get("reservation_id")
                    status = data.get("status")

                    print(f" [MQ] Update received: {res_id} -> {status}")

                    with app.app_context():
                        reservation = db.session.get(Reservation, res_id)
                        if reservation:
                            reservation.status = status
                            db.session.commit()
                        else:
                            print(f" [DB] Reservation {res_id} missing")

                    ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=queue_name, on_message_callback=callback)
                channel.start_consuming()

            except pika.exceptions.AMQPConnectionError:
                print(" [MQ] Connection failed, retrying in 5s...")
                time.sleep(5)
            except Exception as e:
                print(f" [MQ] Error: {e}, retrying in 5s...")
                time.sleep(5)

    thread = threading.Thread(target=listener, daemon=True)
    thread.start()
