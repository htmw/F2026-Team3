import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.errors import register_error_handlers
from database import SessionLocal
from routers import (admin, admin_ai, admin_catalog, admin_integrations, assignments, auth, calendar_feed, conversations, courses, meetings, staff,
                     student_ai, students, users)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

logger = logging.getLogger("acadmate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The institution's time zone (spec 37) is a saved setting; a missing database must not stop the server starting.
    from services import settings as institution
    try:
        with SessionLocal() as db:
            institution.apply_time_zone(db)
    except Exception:
        logger.exception("Could not load the time zone setting; using the default")
    yield


app = FastAPI(title="Acadmate API", version="0.1.0", lifespan=lifespan)
register_error_handlers(app)

# The Vite dev proxy makes the API same-origin; CORS covers direct calls from the frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Feature specs add their routers here.
for router in (auth.router, users.router, students.router, courses.router, student_ai.router, calendar_feed.router,
               assignments.router, conversations.router, staff.router, meetings.router, admin.router,
               admin_ai.router, admin_catalog.router, admin_integrations.router):
    app.include_router(router)


@app.get("/")
def home():
    return {"message": "Acadmate Backend API is running"}


@app.get("/api/v1/health", tags=["Health"])
def health():
    return {"status": "ok"}
