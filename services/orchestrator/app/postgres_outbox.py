"""Transactional PostgreSQL outbox publisher with SKIP LOCKED and DLQ."""
from uuid import uuid4


class PostgresOutboxWorker:
    def __init__(self, connection_factory, publisher, consumer_name="atlantis-outbox"):
        self.connection_factory, self.publisher, self.consumer_name = connection_factory, publisher, consumer_name

    @classmethod
    def from_dsn(cls, dsn: str, publisher, consumer_name="atlantis-outbox"):
        def factory():
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PSYCOPG_NOT_INSTALLED_FROM_APPROVED_LOCK") from exc
            return psycopg.connect(dsn)
        return cls(factory, publisher, consumer_name)

    def publish_batch(self, tenant_id: str, limit=50) -> dict:
        published, failed = 0, 0
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
                cursor.execute(
                    """SELECT id,event_type,payload,correlation_id FROM outbox_event
                       WHERE tenant_id=%s AND published_at IS NULL ORDER BY occurred_at
                       FOR UPDATE SKIP LOCKED LIMIT %s""", (tenant_id, limit))
                for event_id, event_type, payload, correlation_id in cursor.fetchall():
                    try:
                        self.publisher.publish(event_type, payload, str(event_id), str(correlation_id))
                        cursor.execute("UPDATE outbox_event SET published_at=now() WHERE tenant_id=%s AND id=%s", (tenant_id, event_id))
                        published += 1
                    except Exception as exc:
                        cursor.execute(
                            """INSERT INTO dead_letter_event
                               (id,tenant_id,source_event_id,consumer,payload_hash,error_code,error_detail,attempt_count,status)
                               VALUES (%s,%s,%s,%s,encode(digest(%s::text,'sha256'),'hex'),'PUBLISH_FAILURE',%s::jsonb,1,'OPEN')""",
                            (str(uuid4()),tenant_id,event_id,self.consumer_name,payload,'{"redacted":"publisher failure"}'))
                        failed += 1
        return {"published": published, "failed": failed}


class RabbitMQPublisher:
    """Optional AMQP publisher; dependency must come from an approved immutable image."""
    def __init__(self, url: str, exchange="atlantis.events"):
        try:
            import pika
        except ImportError as exc:
            raise RuntimeError("PIKA_NOT_INSTALLED_FROM_APPROVED_LOCK") from exc
        self.pika, self.url, self.exchange = pika, url, exchange

    def publish(self, event_type: str, payload, event_id: str, correlation_id: str):
        import json
        params = self.pika.URLParameters(self.url)
        connection = self.pika.BlockingConnection(params)
        try:
            channel = connection.channel()
            channel.exchange_declare(exchange=self.exchange, exchange_type="topic", durable=True)
            props = self.pika.BasicProperties(content_type="application/json", delivery_mode=2,
                                              message_id=event_id, correlation_id=correlation_id)
            channel.basic_publish(self.exchange, event_type, json.dumps(payload).encode(), properties=props, mandatory=True)
        finally: connection.close()
