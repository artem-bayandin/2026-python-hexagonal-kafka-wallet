from typing import Protocol

from ...messaging.command_envelope import CommandEnvelope


class CommandPublisher(Protocol):
    """Publishes a command envelope under a mandatory routing key.

    Returns only after broker acknowledgement and raises on definitive bounded
    failure; a missing or empty key is rejected by the adapter before network I/O.
    """

    async def publish(self, *, key: str, envelope: CommandEnvelope) -> None: ...
