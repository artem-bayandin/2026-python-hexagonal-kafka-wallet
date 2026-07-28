from typing import Protocol


class OtpService(Protocol):
    def generate_code(self) -> str:
        ...

    def digest(self, normalized_email: str, code: str) -> str:
        ...

    def matches(self, normalized_email: str, code: str, expected_digest: str) -> bool:
        ...
