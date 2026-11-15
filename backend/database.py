from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings

# pool_recycle: hosted Postgres (Neon) closes idle connections when its compute scales to zero.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
