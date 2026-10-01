import json
import logging
import os
import threading
from dotenv import load_dotenv

import pika

load_dotenv()

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
QUEUE_NAME = "click_events"


class RabbitMQPublisher:
    """
    Thread-safe persistent RabbitMQ publisher.
    Reuses a single connection and channel across requests to avoid socket exhaustion
    and stay well within free-tier cloud limits (e.g. CloudAMQP 20 connection cap).
    """

    def __init__(self, url: str, queue: str):
        self.url = url
        self.queue = queue
        self._connection: pika.BlockingConnection | None = None
        self._channel = None
        self._lock = threading.Lock()

    def _get_channel(self):
        if (
            self._connection
            and self._connection.is_open
            and self._channel
            and self._channel.is_open
        ):
            return self._channel

        # Clean up stale connection if exists
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass

        parameters = pika.URLParameters(self.url)
        parameters.socket_timeout = 2.0
        parameters.connection_attempts = 2
        parameters.retry_delay = 1

        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self.queue, durable=True)
        return self._channel

    def publish(self, payload: dict):
        with self._lock:
            channel = self._get_channel()
            channel.basic_publish(
                exchange="",
                routing_key=self.queue,
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                    content_type="application/json",
                ),
            )


_publisher = RabbitMQPublisher(url=RABBITMQ_URL, queue=QUEUE_NAME)


def publish_click_event(
    short_code: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    referer: str | None = None,
):
    """
    Publishes a click event using the shared persistent connection.
    Wrapped in try/except so redirects never fail if RabbitMQ is unavailable.
    """
    try:
        payload = {
            "short_code": short_code,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "referer": referer,
        }
        _publisher.publish(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[RABBITMQ WARNING] Failed to publish click event: {exc}")

