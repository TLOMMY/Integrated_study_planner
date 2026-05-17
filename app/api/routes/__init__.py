from .auth import router as auth_router
from .users import router as users_router
from .study_plans import router as study_plans_router
from .ai import router as ai_router

__all__ = ["auth_router", "users_router", "study_plans_router", "ai_router"]
