
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy.engine import make_url, URL
from langgraph.checkpoint.postgres import PostgresSaver

from src.utils.error_handler import log_info

load_dotenv()


def get_checkpoint_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing from .env"
        )

    parsed_url = make_url(database_url)

    # Convert SQLAlchemy's psycopg2 URL into a
    # PostgreSQL connection string for psycopg3.
    checkpoint_url = URL.create(
        drivername="postgresql",
        username=parsed_url.username,
        password=parsed_url.password,
        host=parsed_url.host,
        port=parsed_url.port,
        database=parsed_url.database,
        query=dict(parsed_url.query)
    )

    return checkpoint_url.render_as_string(
        hide_password=False
    )


@contextmanager
def get_checkpointer():
    connection_string = get_checkpoint_database_url()

    with PostgresSaver.from_conn_string(
        connection_string
    ) as checkpointer:
        yield checkpointer


def initialize_checkpointer():
    with get_checkpointer() as checkpointer:
        checkpointer.setup()

    log_info(
        "PostgreSQL LangGraph checkpoint tables initialized."
    )


if __name__ == "__main__":
    initialize_checkpointer()
    print("LangGraph PostgreSQL checkpointer ready!")
