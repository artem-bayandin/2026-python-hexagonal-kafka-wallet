from datetime import UTC, datetime
from uuid import UUID

import jwt
from pydantic import SecretStr

from app.domain import AUTHENTICATION_FAILED, Result, TokenClaims


class PyJwtTokenService:
    def __init__(self, jwt_secret: SecretStr) -> None:
        self._secret = jwt_secret.get_secret_value()

    def encode(self, user_id: UUID, session_jti: UUID, expires_at: datetime) -> str:
        payload = {
            "sub": str(user_id),
            "jti": str(session_jti),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def decode(self, token: str) -> Result[TokenClaims]:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                options={"require": ["sub", "jti", "exp"]},
            )
            sub = claims["sub"]
            jti = claims["jti"]
            exp = claims["exp"]
            if not isinstance(sub, str) or not isinstance(jti, str):
                raise TypeError("Invalid claim types")
            if isinstance(exp, bool) or not isinstance(exp, int):
                raise TypeError("Invalid exp claim")
            user_id = UUID(sub)
            session_jti = UUID(jti)
            expires_at = datetime.fromtimestamp(exp, tz=UTC)
            return Result.success(
                TokenClaims(
                    user_id=user_id,
                    session_jti=session_jti,
                    expires_at=expires_at,
                )
            )
        except (
            jwt.PyJWTError,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as error:
            return Result.failure(AUTHENTICATION_FAILED, reason=error)
