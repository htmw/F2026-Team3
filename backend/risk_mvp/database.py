"""Only explicitly named loopback disposable demo databases are allowed."""
import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

@lru_cache(maxsize=1)
def engine():
    url=make_url(os.environ['ACADMATE_RISK_DATABASE_URL'])
    if url.host not in {'127.0.0.1','localhost'} or not (url.database or '').startswith('acadmate_risk_demo'):
        raise ValueError('Only loopback acadmate_risk_demo* disposable databases are permitted')
    return create_engine(url,pool_pre_ping=True,isolation_level="REPEATABLE READ")

def session():
    with Session(engine()) as db:yield db
