import sys
from pathlib import Path

from sqlalchemy import inspect, text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import engine


CHAT_MESSAGE_COLUMNS = {
    "status": "VARCHAR(20) NOT NULL DEFAULT 'COMPLETED'",
    "model": "VARCHAR(120)",
    "latency_ms": "INTEGER",
    "input_tokens": "INTEGER",
    "output_tokens": "INTEGER",
    "total_tokens": "INTEGER",
    "error_message": "TEXT",
}


def main() -> None:
    inspector = inspect(engine)
    if "chat_messages" not in inspector.get_table_names():
        print("chat_messages table does not exist yet")
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("chat_messages")
    }

    with engine.begin() as connection:
        for column_name, column_type in CHAT_MESSAGE_COLUMNS.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f"ALTER TABLE chat_messages ADD COLUMN {column_name} {column_type}")
            )
            print(f"added chat_messages.{column_name}")


if __name__ == "__main__":
    main()
