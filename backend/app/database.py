import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load backend/.env regardless of the terminal's current working directory.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/stationery_shop",
)

url = make_url(database_url)
if url.drivername in {"postgres", "postgresql", "postgresql+psycopg2"}:
    url = url.set(drivername="postgresql+psycopg")

connect_args = {}
if url.drivername == "sqlite":
    connect_args["check_same_thread"] = False
elif "psycopg" in url.drivername:
    connect_args["connect_timeout"] = 5

engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def check_db_connection() -> tuple[bool, str]:
    """Test if database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Database connected successfully"
    except Exception as exc:
        return False, str(exc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

