from .auth import router as auth_router
from .health import router as health_router
from .admin import router as admin_router
from .reference import router as reference_router
from .stream import router as stream_router
from .wallet import router as wallet_router

__all__ = [
    "admin_router",
    "auth_router",
    "health_router",
    "reference_router",
    "stream_router",
    "wallet_router",
]
