import ssl
from typing import Any

from aiokafka import AIOKafkaProducer

from app.config import KafkaSettings

from .producer import KafkaCommandPublisher


def _build_ssl_context(settings: KafkaSettings) -> ssl.SSLContext:
    # create_default_context enforces certificate and hostname verification;
    # neither is disableable here by design.
    context = ssl.create_default_context(cafile=settings.ssl_ca_file)
    if settings.ssl_cert_file is not None and settings.ssl_key_file is not None:
        context.load_cert_chain(settings.ssl_cert_file, settings.ssl_key_file)
    return context


def build_aiokafka_producer(settings: KafkaSettings) -> AIOKafkaProducer:
    options: dict[str, Any] = {}
    if settings.security_protocol.startswith("SASL"):
        options["sasl_mechanism"] = settings.sasl_mechanism
        if settings.sasl_username is not None:
            options["sasl_plain_username"] = settings.sasl_username.get_secret_value()
        if settings.sasl_password is not None:
            options["sasl_plain_password"] = settings.sasl_password.get_secret_value()
    if settings.security_protocol in ("SSL", "SASL_SSL"):
        options["ssl_context"] = _build_ssl_context(settings)
    return AIOKafkaProducer(
        bootstrap_servers=settings.bootstrap_servers,
        # Fixed Version 2 guarantees; intentionally not configurable.
        acks="all",
        enable_idempotence=True,
        request_timeout_ms=settings.producer_request_timeout_ms,
        retry_backoff_ms=settings.producer_retry_backoff_ms,
        security_protocol=settings.security_protocol,
        **options,
    )


def build_kafka_command_publisher(
    settings: KafkaSettings,
    *,
    topic: str | None = None,
) -> KafkaCommandPublisher:
    return KafkaCommandPublisher(
        build_aiokafka_producer(settings),
        topic or settings.command_topic,
        max_retries=settings.producer_max_retries,
        retry_backoff_ms=settings.producer_retry_backoff_ms,
        retry_backoff_max_ms=settings.producer_retry_backoff_max_ms,
        delivery_timeout_ms=settings.producer_delivery_timeout_ms,
    )


__all__ = [
    "build_aiokafka_producer",
    "build_kafka_command_publisher",
]
