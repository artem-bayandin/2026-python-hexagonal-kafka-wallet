# import os
from functools import lru_cache
from typing import Annotated, Literal, NamedTuple, Self

from pydantic import BeforeValidator, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# other environments are not supported yet
AppEnv = Literal["development"]  # , "test", "production"]
# other security protocols are not supported yet
SecurityProtocol = Literal["PLAINTEXT"]  # , "SSL", "SASL_PLAINTEXT", "SASL_SSL"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_ENV_FILE = ".env"
_DEFAULT_KAFKA_SECURITY_PROTOCOL: SecurityProtocol = "PLAINTEXT"


def _empty_to_none(value: object) -> object:
    # Empty environment values mean "missing" per the configuration contract.
    if isinstance(value, str) and not value.strip():
        return None
    return value


OptionalStr = Annotated[str | None, BeforeValidator(_empty_to_none)]
OptionalSecret = Annotated[SecretStr | None, BeforeValidator(_empty_to_none)]


class SharedSettings(BaseSettings):
    """Settings every backend process owns (database connectivity and logging)."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    app_env: AppEnv
    database_url: str
    log_level: LogLevel


class ApiSettings(SharedSettings):
    """API-owned settings; extends the shared group with HTTP/auth concerns."""

    jwt_secret: SecretStr
    jwt_access_token_ttl_minutes: int
    otp_hmac_secret: SecretStr
    otp_ttl_seconds: int
    otp_max_attempts: int
    enable_demo_otp: bool = False
    admin_api_key: OptionalStr = None
    cors_allowed_origins: str

    @model_validator(mode="after")
    def _reject_prohibited_shortcuts(self) -> Self:
        if self.enable_demo_otp and self.app_env != "development":
            raise ValueError("ENABLE_DEMO_OTP=true is allowed only when APP_ENV=development")
        if self.app_env == "production" and self.admin_api_key is not None:
            raise ValueError("ADMIN_API_KEY is forbidden when APP_ENV=production")
        return self


class KafkaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_prefix="KAFKA_", extra="ignore")

    # base
    bootstrap_servers: str
    command_topic: str
    dlq_topic: str
    worker_group_id: str
    # other
    security_protocol: SecurityProtocol = _DEFAULT_KAFKA_SECURITY_PROTOCOL
    # sasl_mechanism: OptionalStr = None
    # sasl_username: OptionalSecret = None
    # sasl_password: OptionalSecret = None
    # ssl_ca_file: OptionalStr = None
    # ssl_cert_file: OptionalStr = None
    # ssl_key_file: OptionalStr = None
    producer_request_timeout_ms: int = Field(default=10000, gt=0)
    producer_delivery_timeout_ms: int = Field(default=30000, gt=0)
    producer_max_retries: int = Field(default=5, ge=0)
    producer_retry_backoff_ms: int = Field(default=200, gt=0)
    producer_retry_backoff_max_ms: int = Field(default=2000, gt=0)

    @field_validator("bootstrap_servers")
    @classmethod
    def _bootstrap_servers_non_empty(cls, value: str) -> str:
        endpoints = [endpoint.strip() for endpoint in value.split(",")]
        if not all(endpoints):
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS must be non-empty comma-separated endpoints")
        return ",".join(endpoints)

    @model_validator(mode="after")
    def _validate_kafka_invariants(self) -> Self:
        if self.dlq_topic == self.command_topic:
            raise ValueError("Command and DLQ topics must be distinct")
        if self.producer_delivery_timeout_ms < self.producer_request_timeout_ms:
            raise ValueError(
                "KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS must be at least "
                "KAFKA_PRODUCER_REQUEST_TIMEOUT_MS"
            )
        if self.producer_retry_backoff_max_ms < self.producer_retry_backoff_ms:
            raise ValueError(
                "KAFKA_PRODUCER_RETRY_BACKOFF_MAX_MS must not be less than "
                "KAFKA_PRODUCER_RETRY_BACKOFF_MS"
            )
        # self._validate_security_pairs()
        return self

    # def _validate_security_pairs(self) -> None:
    #     sasl_selected = self.security_protocol in ("SASL_PLAINTEXT", "SASL_SSL")
    #     sasl_fields = (self.sasl_mechanism, self.sasl_username, self.sasl_password)
    #     if sasl_selected and any(field is None for field in sasl_fields):
    #         raise ValueError(
    #             "KAFKA_SASL_MECHANISM, KAFKA_SASL_USERNAME, and KAFKA_SASL_PASSWORD "
    #             "are all required when a SASL security protocol is selected"
    #         )
    #     if not sasl_selected and any(field is not None for field in sasl_fields):
    #         raise ValueError("KAFKA_SASL_* settings require a SASL security protocol")
    #     if (self.ssl_cert_file is None) != (self.ssl_key_file is None):
    #         raise ValueError("KAFKA_SSL_CERT_FILE and KAFKA_SSL_KEY_FILE must be set as a pair")


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_prefix="WORKER_", extra="ignore")

    max_attempts: int = Field(default=3, ge=1)
    retry_backoff_ms: int = Field(default=500, gt=0)
    retry_backoff_max_ms: int = Field(default=5000, gt=0)
    poll_timeout_ms: int = Field(default=1000, gt=0)
    heartbeat_interval_ms: int = Field(default=3000, gt=0)
    session_timeout_ms: int = Field(default=30000, gt=0)
    max_poll_interval_ms: int = Field(default=300000, gt=0)

    @model_validator(mode="after")
    def _validate_worker_invariants(self) -> Self:
        if self.retry_backoff_max_ms < self.retry_backoff_ms:
            raise ValueError(
                "WORKER_RETRY_BACKOFF_MAX_MS must not be less than WORKER_RETRY_BACKOFF_MS"
            )
        if self.heartbeat_interval_ms >= self.session_timeout_ms:
            raise ValueError("WORKER_HEARTBEAT_INTERVAL_MS must be below WORKER_SESSION_TIMEOUT_MS")
        # Worst-case time between polls must stay below max.poll.interval: one poll
        # wait plus the full local retry schedule (execution and DLQ waits are bounded
        # separately and checked in validate_worker_composition).
        worst_case_retry_ms = (self.max_attempts - 1) * self.retry_backoff_max_ms
        if self.max_poll_interval_ms <= self.poll_timeout_ms + worst_case_retry_ms:
            raise ValueError(
                "WORKER_MAX_POLL_INTERVAL_MS must cover one poll plus the full retry schedule"
            )
        return self

    @property
    def submitted_visibility_delay_ms(self) -> int:
        """Short bounded delay before classifying a still-``submitted`` row (not an env var)."""
        return self.retry_backoff_ms


class ReaperSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_prefix="REAPER_", extra="ignore")

    interval_seconds: int = Field(default=30, gt=0)
    stale_threshold_seconds: int = Field(default=60, gt=0)
    batch_size: int = Field(default=100, ge=1, le=1000)


class StreamingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    admin_long_poll_default_seconds: int = Field(default=25, ge=0)
    admin_long_poll_max_seconds: int = Field(default=30, gt=0)
    sse_heartbeat_interval_seconds: int = Field(default=15, gt=0)
    sse_retry_milliseconds: int = Field(default=3000, ge=3000)

    @model_validator(mode="after")
    def _validate_streaming_invariants(self) -> Self:
        if self.admin_long_poll_default_seconds > self.admin_long_poll_max_seconds:
            raise ValueError(
                "ADMIN_LONG_POLL_DEFAULT_SECONDS must not exceed ADMIN_LONG_POLL_MAX_SECONDS"
            )
        return self


# def _require_readable_file(path: str | None, field_name: str) -> None:
#     if path is None:
#         raise ValueError(f"{field_name} is required when APP_ENV=production")
#     if not os.path.isfile(path) or not os.access(path, os.R_OK):
#         raise ValueError(f"{field_name} must point to a readable file")


def validate_kafka_connection(kafka: KafkaSettings, *, app_env: AppEnv) -> None:
    """Cross-group production invariants for the broker connection."""
    if app_env != "production":
        return
    # if kafka.security_protocol not in ("SSL", "SASL_SSL"):
    #    raise ValueError("KAFKA_SECURITY_PROTOCOL must be SSL or SASL_SSL when APP_ENV=production")
    # _require_readable_file(kafka.ssl_ca_file, "KAFKA_SSL_CA_FILE")
    # if kafka.ssl_cert_file is not None:
    #     _require_readable_file(kafka.ssl_cert_file, "KAFKA_SSL_CERT_FILE")
    #     _require_readable_file(kafka.ssl_key_file, "KAFKA_SSL_KEY_FILE")


def validate_worker_composition(kafka: KafkaSettings, worker: WorkerSettings) -> None:
    """max.poll.interval must additionally cover the bounded DLQ publication wait."""
    worst_case_retry_ms = (worker.max_attempts - 1) * worker.retry_backoff_max_ms
    worst_case_ms = (
        worker.poll_timeout_ms + worst_case_retry_ms + kafka.producer_delivery_timeout_ms
    )
    if worker.max_poll_interval_ms <= worst_case_ms:
        raise ValueError(
            "WORKER_MAX_POLL_INTERVAL_MS must cover polling, the full retry schedule, "
            "and the bounded DLQ publication wait"
        )


def validate_reaper_composition(kafka: KafkaSettings, reaper: ReaperSettings) -> None:
    """The stale threshold must not race a normally completing bounded publish."""
    if reaper.stale_threshold_seconds * 1000 <= kafka.producer_delivery_timeout_ms:
        raise ValueError(
            "REAPER_STALE_THRESHOLD_SECONDS must exceed the producer delivery bound plus jitter"
        )


@lru_cache
def get_api_settings() -> ApiSettings:
    return ApiSettings()  # type: ignore[call-arg]


@lru_cache
def get_kafka_settings() -> KafkaSettings:
    return KafkaSettings()  # type: ignore[call-arg]


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()


@lru_cache
def get_reaper_settings() -> ReaperSettings:
    return ReaperSettings()


@lru_cache
def get_streaming_settings() -> StreamingSettings:
    return StreamingSettings()


class ApiRuntime(NamedTuple):
    api: ApiSettings
    kafka: KafkaSettings
    streaming: StreamingSettings


class WorkerRuntime(NamedTuple):
    settings: SharedSettings
    kafka: KafkaSettings
    worker: WorkerSettings


class ReaperRuntime(NamedTuple):
    settings: SharedSettings
    kafka: KafkaSettings
    reaper: ReaperSettings


@lru_cache
def load_api_runtime() -> ApiRuntime:
    runtime = ApiRuntime(get_api_settings(), get_kafka_settings(), get_streaming_settings())
    validate_kafka_connection(runtime.kafka, app_env=runtime.api.app_env)
    return runtime


@lru_cache
def load_worker_runtime() -> WorkerRuntime:
    runtime = WorkerRuntime(
        SharedSettings(),  # type: ignore[call-arg]
        get_kafka_settings(),
        get_worker_settings(),
    )
    validate_kafka_connection(runtime.kafka, app_env=runtime.settings.app_env)
    validate_worker_composition(runtime.kafka, runtime.worker)
    return runtime


@lru_cache
def load_reaper_runtime() -> ReaperRuntime:
    runtime = ReaperRuntime(
        SharedSettings(),  # type: ignore[call-arg]
        get_kafka_settings(),
        get_reaper_settings(),
    )
    validate_kafka_connection(runtime.kafka, app_env=runtime.settings.app_env)
    validate_reaper_composition(runtime.kafka, runtime.reaper)
    return runtime


__all__ = [
    "ApiRuntime",
    "AppEnv",
    "KafkaSettings",
    "LogLevel",
    "ReaperRuntime",
    "ReaperSettings",
    "SecurityProtocol",
    "ApiSettings",
    "SharedSettings",
    "StreamingSettings",
    "WorkerRuntime",
    "WorkerSettings",
    "get_kafka_settings",
    "get_reaper_settings",
    "get_api_settings",
    "get_streaming_settings",
    "get_worker_settings",
    "load_api_runtime",
    "load_reaper_runtime",
    "load_worker_runtime",
    "validate_kafka_connection",
    "validate_reaper_composition",
    "validate_worker_composition",
]
