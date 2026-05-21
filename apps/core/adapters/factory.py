import uuid
import pymysql
import psycopg2
import cx_Oracle
import pymongo
import sqlite3
from abc import ABC, abstractmethod


class EngineAdapter(ABC):
    @abstractmethod
    def test_connection(self):
        return False, "Not implemented"

    @abstractmethod
    def get_schema(self):
        return {}

    @abstractmethod
    def execute(self, sql, params=None):
        return [], []


class MySQLAdapter(EngineAdapter):
    def __init__(self, host, port, dbname, username, password, **kwargs):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.username = username
        self.password = password
        self.kwargs = kwargs

    def test_connection(self):
        try:
            conn = pymysql.connect(
                host=self.host, port=self.port, database=self.dbname,
                user=self.username, password=self.password, connect_timeout=5,
            )
            conn.close()
            return True, "MySQL connected"
        except Exception as exc:
            return False, str(exc)

    def get_schema(self):
        return {"tables": []}

    def execute(self, sql, params=None):
        conn = pymysql.connect(
            host=self.host, port=self.port, database=self.dbname,
            user=self.username, password=self.password,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                cols = [c[0] for c in cur.description] if cur.description else []
                rows = [list(r) for r in cur.fetchall()]
            return cols, rows
        finally:
            conn.close()


class PostgreSQLAdapter(EngineAdapter):
    def __init__(self, host, port, dbname, username, password, **kwargs):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.username = username
        self.password = password
        self.kwargs = kwargs

    def test_connection(self):
        try:
            conn = psycopg2.connect(
                host=self.host, port=self.port, dbname=self.dbname,
                user=self.username, password=self.password, connect_timeout=5,
            )
            conn.close()
            return True, "PostgreSQL connected"
        except Exception as exc:
            return False, str(exc)

    def get_schema(self):
        return {"tables": []}

    def execute(self, sql, params=None):
        conn = psycopg2.connect(
            host=self.host, port=self.port, dbname=self.dbname,
            user=self.username, password=self.password,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                cols = [c[0] for c in cur.description] if cur.description else []
                rows = [list(r) for r in cur.fetchall()]
            return cols, rows
        finally:
            conn.close()


class SQLiteAdapter(EngineAdapter):
    def __init__(self, dbname, **kwargs):
        self.dbname = dbname

    def test_connection(self):
        try:
            conn = sqlite3.connect(self.dbname)
            conn.close()
            return True, "SQLite connected"
        except Exception as exc:
            return False, str(exc)

    def get_schema(self):
        return {"tables": []}

    def execute(self, sql, params=None):
        conn = sqlite3.connect(self.dbname)
        try:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
            conn.commit()
            return cols, rows
        finally:
            conn.close()


class OracleAdapter(EngineAdapter):
    def __init__(self, host, port, dbname, username, password, **kwargs):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.username = username
        self.password = password

    def test_connection(self):
        try:
            dsn = f"{self.host}:{self.port}/{self.dbname}"
            conn = cx_Oracle.connect(self.username, self.password, dsn)
            conn.close()
            return True, "Oracle connected"
        except Exception as exc:
            return False, str(exc)

    def get_schema(self):
        return {"tables": []}

    def execute(self, sql, params=None):
        dsn = f"{self.host}:{self.port}/{self.dbname}"
        conn = cx_Oracle.connect(self.username, self.password, dsn)
        try:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
            return cols, rows
        finally:
            conn.close()


class MongoDBAdapter(EngineAdapter):
    def __init__(self, host, port, dbname, username, password, **kwargs):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.username = username
        self.password = password

    def test_connection(self):
        try:
            uri = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/"
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.server_info()
            client.close()
            return True, "MongoDB connected"
        except Exception as exc:
            return False, str(exc)

    def get_schema(self):
        return {"collections": []}

    def execute(self, sql, params=None):
        return [], [{"note": "MongoDB queries use aggregation pipeline, not raw SQL"}]


class EngineFactory:
    _adapters = {
        "mysql": MySQLAdapter,
        "mariadb": MySQLAdapter,
        "postgresql": PostgreSQLAdapter,
        "cockroachdb": PostgreSQLAdapter,
        "sqlite": SQLiteAdapter,
        "oracle": OracleAdapter,
        "mongodb": MongoDBAdapter,
    }

    @classmethod
    def create(cls, engine, host, port, dbname, username, password, **kwargs):
        adapter_cls = cls._adapters.get(engine.lower())
        if not adapter_cls:
            return None
        return adapter_cls(host=host, port=port, dbname=dbname,
                           username=username, password=password, **kwargs)
