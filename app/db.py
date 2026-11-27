import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

URL = os.getenv("DATABASE_URL", "sqlite:///./mobihub_local.db")  # SQLite for local/offline mode
for prefix in ("postgres://", "postgresql://"):
    if URL.startswith(prefix):
        URL = "postgresql+psycopg://" + URL[len(prefix):]

engine = create_engine(
    URL,
    connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
Session = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()
