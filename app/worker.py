import json
import logging
import os
import time
from dotenv import load_dotenv

import pika

load_dotenv()
from app.database import Base, SessionLocal, engine
from app.models import ClickEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("analytics_worker")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
QUEUE_NAME = "click_events"

# Ensure tables are created
Base.metadata.create_all(bind=engine)


def process_message(ch, method, properties, body):
    """
    Consumer callback: parses JSON payload and saves click analytics to PostgreSQL.
    """
    try:
        data = json.loads(body.decode("utf-8"))
        logger.info(f"Received click event: {data}")

        db = SessionLocal()
        try:
            event = ClickEvent(
                short_code=data.get("short_code"),
                ip_address=data.get("ip_address"),
                user_agent=data.get("user_agent"),
                referer=data.get("referer"),
            )
            db.add(event)
            db.commit()
            logger.info(f"Saved analytics for '{data.get('short_code')}' to PostgreSQL (Event ID: {event.id})")
        finally:
            db.close()

        # Acknowledge that message was successfully processed
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        logger.error(f"Error processing message: {exc}")
        # Reject and requeue or log
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    logger.info("Starting RabbitMQ Analytics Worker...")
    parameters = pika.URLParameters(RABBITMQ_URL)

    # Retry connection with backoff while RabbitMQ is starting up
    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)

            # Fair dispatch: only deliver 1 unacknowledged message to worker at a time
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_message)

            logger.info(f"Connected to RabbitMQ! Waiting for messages in queue '{QUEUE_NAME}'. To exit press CTRL+C")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as err:
            logger.warning(f"RabbitMQ broker not ready yet ({err}). Retrying in 3 seconds...")
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Stopping worker...")
            break


if __name__ == "__main__":
    start_worker()
