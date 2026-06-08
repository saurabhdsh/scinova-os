from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def get_database_url() -> str:
    if settings.sqlite_fallback:
        try:
            import psycopg2

            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                dbname="scinova",
                user="scinova",
                password="scinova",
                connect_timeout=2,
            )
            conn.close()
            return settings.database_url
        except Exception:
            return "sqlite:///./scinova.db"
    return settings.database_url


DATABASE_URL = get_database_url()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
