import os
import json
import time
import pika
import stripe

def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value

RABBITMQ_HOST = _get_env("RABBITMQ_HOST")
MQ_QUEUE_REQUESTS = _get_env("MQ_QUEUE_REQUESTS")
MQ_EXCHANGE_EVENTS = _get_env("MQ_EXCHANGE_EVENTS")

STRIPE_API_KEY = _get_env("STRIPE_API_KEY")
STRIPE_API_BASE = _get_env("STRIPE_API_BASE")

stripe.api_key = STRIPE_API_KEY
stripe.api_base = STRIPE_API_BASE

def process_payment_request(ch, method, properties, body):
    payload = json.loads(body)
    print(f" [MQ] Received payment request: {payload}")

    try:
        # Simulate call to Stripe
        stripe.Charge.create(
            amount=payload.get("amount", 1000),
            currency=payload.get("currency", "usd"),
            source="tok_visa",
            description=f"Reservation {payload.get('reservation_id')}"
        )
        status = "PAID"
    except Exception as e:
        print(f" [Stripe] Error: {e}")
        status = "FAILED"

    result_event = {
        "reservation_id": payload["reservation_id"],
        "user_id": payload["user_id"],
        "status": status,
        "amount": payload.get("amount"),
        "timestamp": time.time()
    }
    
    publish_result(ch, result_event)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def publish_result(ch, event):
    ch.exchange_declare(exchange=MQ_EXCHANGE_EVENTS, exchange_type='fanout')
    ch.basic_publish(
        exchange=MQ_EXCHANGE_EVENTS,
        routing_key='',
        body=json.dumps(event)
    )
    print(f" [MQ] Published event: {event['status']}")

def run():
    print(f" [Worker] Connecting to {RABBITMQ_HOST}...")
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()

            channel.queue_declare(queue=MQ_QUEUE_REQUESTS, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=MQ_QUEUE_REQUESTS, on_message_callback=process_payment_request)

            print(" [Worker] Waiting for requests...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print(" [Worker] Connection failed, retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f" [Worker] Error: {e}, retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    run()
