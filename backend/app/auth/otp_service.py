import hashlib
import hmac
import secrets

from pydantic import SecretStr


class HmacOtpService:
    def __init__(self, otp_hmac_secret: SecretStr) -> None:
        self._secret = otp_hmac_secret.get_secret_value().encode()

    def generate_code(self) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def digest(self, normalized_email: str, code: str) -> str:
        message = f"{normalized_email}:{code}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    def matches(
        self,
        normalized_email: str,
        code: str,
        expected_digest: str,
    ) -> bool:
        return hmac.compare_digest(
            self.digest(normalized_email, code),
            expected_digest,
        )
