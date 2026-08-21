import logging
from aiokafka import AIOKafkaProducer

from app.domain import WalletTxMessage

from .dlq_mapper import DlqMapper
from .dlq_context import DlqContext

logger = logging.getLogger(__name__)


class DlqPublisher:
    def __init__(
        self,
        producer: AIOKafkaProducer,
        topic: str,
        # *,
    ) -> None:
        self._producer = producer
        self._topic = topic

    async def publish_failure(
        self,
        *,
        key: str,
        message: WalletTxMessage | None,
        context: DlqContext,
    ) -> None:
        payload = DlqMapper.dlq_payload_to_json(key=key, message=message, context=context)
        log_extra = {
            "request_id": context.request_id,
            "msg_tx_type": context.msg_tx_type,
            "failure_classification": context.failure_classification,
            "attempt_count": str(context.attempt_count),
        }
        logger.info("dlq publish attempt", extra=log_extra)
        try:
            await self._producer.send_and_wait(
                self._topic,
                key=key.encode("utf-8"),
                value=payload,
            )
        except Exception:
            logger.exception(
                "dlq publish failed; source record must remain unacknowledged",
                extra=log_extra,
                exc_info=True,
            )
            raise
        logger.info("dlq publish acknowledged", extra=log_extra)
