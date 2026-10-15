import importlib.util
import sqlite3
from pathlib import Path


HANDLER = Path(__file__).parent / "handler.py"


def load():
    spec = importlib.util.spec_from_file_location("database_inspect_handler", HANDLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
        connection.execute("CREATE INDEX users_email_idx ON users(email)")
        connection.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id))")
        connection.execute("INSERT INTO users(email) VALUES ('person@example.test')")


def test_inspects_schema_and_row_counts_without_writes(tmp_path):
    database = tmp_path / "app.db"
    make_database(database)

    result = load().run({"path": str(database), "include_row_counts": True})

    assert result["error"] is None
    assert result["result"]["read_only"] is True
    users = next(table for table in result["result"]["tables"] if table["name"] == "users")
    assert users["row_count"] == 1
    assert users["columns"][0]["name"] == "id"
    assert users["indexes"][0]["name"] == "users_email_idx"


def test_unknown_table_returns_actionable_error(tmp_path):
    database = tmp_path / "app.db"
    make_database(database)
    result = load().run({"path": str(database), "table": "missing"})
    assert result["result"] is None
    assert result["error"] == "Table not found: missing"
