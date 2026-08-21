from typing import Protocol

from ...messaging import WalletTxMessage


class MessagePublisher(Protocol):
    """Publishes a wallet tx message under a mandatory routing key.

    Returns only after broker acknowledgement and raises on definitive bounded
    failure; a missing or empty key is rejected by the adapter before network I/O.
    """

    async def publish(self, *, key: str, message: WalletTxMessage) -> None: ...
