from .user import router as user_router
from .inline import router as inline_router
from .admin import router as admin_router
from .subscription import router as subscription_router
from .payment import router as payment_router

__all__ = [
    "user_router",
    "inline_router",
    "admin_router",
    "subscription_router",
    "payment_router"
]
