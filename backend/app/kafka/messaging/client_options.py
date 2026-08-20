# import ssl
from typing import Any

from app.config import KafkaSettings


# def _build_ssl_context(settings: KafkaSettings) -> ssl.SSLContext:
#     # create_default_context enforces certificate and hostname verification;
#     # neither is disableable here by design.
#     context = ssl.create_default_context(cafile=settings.ssl_ca_file)
#     if settings.ssl_cert_file is not None and settings.ssl_key_file is not None:
#         context.load_cert_chain(settings.ssl_cert_file, settings.ssl_key_file)
#     return context


def build_kafka_client_kwargs(settings: KafkaSettings) -> dict[str, Any]:
    """Connection options shared by Kafka producers and consumers."""
    options: dict[str, Any] = {
        "bootstrap_servers": settings.bootstrap_servers,
        "security_protocol": settings.security_protocol,
    }
    # if settings.security_protocol.startswith("SASL"):
    #     options["sasl_mechanism"] = settings.sasl_mechanism
    #     if settings.sasl_username is not None:
    #         options["sasl_plain_username"] = settings.sasl_username.get_secret_value()
    #     if settings.sasl_password is not None:
    #         options["sasl_plain_password"] = settings.sasl_password.get_secret_value()
    # if settings.security_protocol in ("SSL", "SASL_SSL"):
    #     options["ssl_context"] = _build_ssl_context(settings)
    return options


__all__ = ["build_kafka_client_kwargs"]
