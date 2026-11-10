
import os
import logging

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

from src.utils.error_handler import handle_error, log_info


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")


# ==========================================
# DATABASE ENGINE
# ==========================================

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "connect_timeout": 10
    }
)


# ==========================================
# SESSION CONFIGURATION
# ==========================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()


# ==========================================
# DATABASE CONNECTION TEST
# ==========================================

def test_database_connection():

    try:

        with engine.connect() as connection:

            result = connection.execute(
                text("SELECT 1")
            )

            log_info("PostgreSQL connection successful.")

            return result.scalar() == 1

    except SQLAlchemyError as error:

        handle_error(
            error,
            context="PostgreSQL Connection"
        )

        return False


# ==========================================
# DATABASE SESSION DEPENDENCY
# ==========================================

def get_db():

    db = SessionLocal()

    try:

        yield db

    except Exception as error:

        db.rollback()

        handle_error(
            error,
            context="Database Session"
        )

        raise

    finally:

        db.close()


if __name__ == "__main__":

    if test_database_connection():

        print("Database connection successful!")

    else:

        print("Database connection failed. Check application.log.")
