import importlib.util
import sqlite3
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("database_query_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selects_but_rejects_writes(tmp_path):
    database = tmp_path / "app.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE values_table (value TEXT)")
        connection.execute("INSERT INTO values_table VALUES ('safe')")
    handler = load()
    selected = handler.run({"path": str(database), "query": "SELECT value FROM values_table"})
    blocked = handler.run({"path": str(database), "query": "DELETE FROM values_table"})
    assert selected["result"]["rows"] == [{"value": "safe"}]
    assert "Only a single SELECT" in blocked["error"]
