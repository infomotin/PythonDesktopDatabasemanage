import uuid
from datetime import datetime

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.db import connections, transaction
import logging

logger = logging.getLogger(__name__)

ENGINE_ALIASES = {
    "mysql": "mysql",
    "mariadb": "mysql",
    "postgresql": "postgresql",
    "cockroachdb": "postgresql",
    "sqlserver": "mssql",
    "oracle": "oracle",
    "mongodb": "mongodb",
    "sqlite": "sqlite",
}


def create_django_engine(engine: str) -> str:
    aliases = {
        "mysql": "django.db.backends.mysql",
        "postgresql": "django.db.backends.postgresql",
        "sqlserver": "sql_server.pyodbc",
        "oracle": "django.db.backends.oracle",
        "sqlite": "django.db.backends.sqlite3",
    }
    aliases.update(settings.DATABASES.get("default", {}).get("ENGINE_MAP", {}))
    return aliases.get(engine, f"django.db.backends.{engine}")


def build_connection_config(conn) -> dict:
    from apps.core.crypto import decrypt_credential

    password = ""
    if conn.password:
        try:
            password = decrypt_credential(conn.password)
        except Exception:
            password = ""

    config = {
        "ENGINE": create_django_engine(conn.engine),
        "NAME": conn.dbname,
        "USER": conn.username or "",
        "PASSWORD": password,
        "HOST": conn.host,
        "PORT": conn.port,
        "OPTIONS": {},
    }

    if conn.engine == "mysql":
        config["OPTIONS"] = {"init_command": "SET sql_mode='STRICT_TRANS_TABLES'"}
    elif conn.engine == "postgresql":
        pass
    elif conn.engine == "sqlserver":
        config["OPTIONS"] = {"driver": "ODBC Driver 17 for SQL Server", "extra_params": "TrustServerCertificate=yes"}

    return config


CACHE = {}
TTL = 300


class ConnectionPool:
    @staticmethod
    def get(conn):
        conn_id = str(conn.id)
        now = datetime.now().timestamp()
        cached = CACHE.get(conn_id)
        if cached:
            alias, ts = cached
            if now - ts < TTL:
                return alias
            try:
                connections[alias].close()
            except Exception:
                pass
        alias = f"dynamic_{conn_id}"
        config = build_connection_config(conn)
        connections.databases[alias] = config
        CACHE[conn_id] = (alias, now)
        return alias

    @staticmethod
    def test(conn):
        try:
            alias = ConnectionPool.get(conn)
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT 1")
            return "connected"
        except Exception as e:
            try:
                alias = ConnectionPool.get(conn)
                connections[alias].close()
                if conn_id := str(conn.id):
                    CACHE.pop(conn_id, None)
            except Exception:
                pass
            return f"error: {e}"

    @staticmethod
    def invalidate(conn):
        conn_id = str(conn.id)
        CACHE.pop(conn_id, None)
        try:
            alias = ConnectionPool.get(conn)
            connections[alias].close()
        except Exception:
            pass

    @staticmethod
    def close_all():
        for alias, _ in CACHE.values():
            try:
                connections[alias].close()
            except Exception:
                pass
        CACHE.clear()


def test_connection(engine: str, host: str, port: int, dbname: str, username: str, password: str) -> tuple:
    try:
        from apps.core.adapters.factory import EngineFactory
        adapter = EngineFactory.create(engine, host, port, dbname, username, password)
        return adapter.test_connection()
    except ImportError:
        return _validate_connection(engine, host, port, dbname, username, password)


def _validate_connection(engine: str, host: str, port: int, dbname: str, username: str, password: str) -> tuple:
    try: import pymongo; mongo_ok = True
    except ImportError: mongo_ok = False

    try: import mysql.connector; mysql_ok = True
    except ImportError: mysql_ok = False

    try: import psycopg2; pg_ok = True
    except ImportError: pg_ok = False

    try: import cx_Oracle; oracle_ok = True
    except ImportError: oracle_ok = False

    if engine == "mysql" and mysql_ok:
        import mysql.connector
        conn = mysql.connector.connect(host=host, port=port, database=dbname, user=username, password=password, connect_timeout=5)
        conn.close()
        return True, "Connected"
    if engine == "postgresql" and pg_ok:
        import psycopg2
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=username, password=password, connect_timeout=5)
        conn.close()
        return True, "Connected"
    if engine == "oracle" and oracle_ok:
        cx_Oracle.init_oracle_client()
        conn = cx_Oracle.connect(user=username, password=password, dsn=f"{host}:{port}/{dbname}", encoding="UTF-8")
        conn.close()
        return True, "Connected"
    if engine == "sqlite":
        import sqlite3; sqlite3.connect(dbname).close()
        return True, "Connected"
    if engine == "mongodb" and mongo_ok:
        uri = f"mongodb://{username}:{password}@{host}:{port}/{dbname}?authSource=admin"
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        client.close()
        return True, "Connected"
    if engine in ("mysql", "mariadb"):
        return False, "Database driver not installed (mysql.connector). Run: pip install mysql-connector-python"
    if engine in ("postgresql", "cockroachdb"):
        return False, "Database driver not installed (psycopg2). Run: pip install psycopg2-binary"
    if engine == "oracle":
        return False, "Database driver not installed (cx_Oracle). Run: pip install cx-Oracle"
    if engine == "mongodb":
        return False, "Database driver not installed (pymongo). Run: pip install pymongo"
    return False, f"Unknown or unsupported engine: {engine}"
