from django.core.paginator import Paginator
from django.db import models
from django.utils import timezone

from apps.core.utils.query_parser import QueryParser
from apps.core.utils.data_processor import DataProcessor


class QueryExecutor:
    def __init__(self, connection):
        self.connection = connection
        self.cursor = None

    def __enter__(self):
        self.cursor = self.connection.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if exc_type:
            self.connection.rollback()
        return False

    def execute(self, sql: str, params: tuple = ()):
        self.cursor.execute(sql, params)
        self.connection.commit()
        return self.cursor.rowcount

    def execute_many(self, sql: str, params: list):
        self.cursor.executemany(sql, params)
        self.connection.commit()
        return self.cursor.rowcount

    def fetch_query(self, sql: str, params: tuple = ()):
        self.cursor.execute(sql, params)
        columns = [col[0] for col in self.cursor.description] if self.cursor.description else []
        rows = [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        return rows, columns

    def fetch_all(self, sql: str):
        self.cursor.execute(sql)
        return [dict(zip([col[0] for col in self.cursor.description], row))
                for row in self.cursor.fetchall()]

    def get_tables(self):
        raise NotImplementedError

    def get_table_info(self, table_name: str):
        raise NotImplementedError

    def get_procedure_list(self):
        return []

    def create_database(self, db_name: str):
        raise NotImplementedError


class SqlExecutor(QueryExecutor):
    def get_tables(self):
        sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()"
        rows = self.fetch_all(sql)
        return [r["table_name"] for r in rows]

    def get_table_info(self, table_name: str):
        sql = f"SELECT column_name, data_type, is_nullable, column_default, ordinal_position, column_key" \
              f" FROM information_schema.columns WHERE table_name = '{table_name}' AND table_schema = DATABASE()"
        rows = self.fetch_all(sql)
        return [{
            "name": r["column_name"],
            "type": r["data_type"],
            "nullable": r["is_nullable"] == "YES",
            "default": r.get("column_default"),
            "pk": r.get("column_key") == "PRI",
            "fk": r.get("column_key") == "MUL",
        } for r in rows]

    def get_procedure_list(self):
        sql = "SELECT procedure_name FROM information_schema.procedures WHERE procedure_schema = DATABASE()"
        rows = self.fetch_all(sql)
        return [r["procedure_name"] for r in rows]

    def create_database(self, db_name: str):
        self.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        return True

    def get_table_columns(self, table_name: str):
        sql = f"SHOW COLUMNS FROM `{table_name}`"
        return self.fetch_all(sql)

    def get_table_indexes(self, table_name: str):
        sql = f"SHOW INDEX FROM `{table_name}`"
        return self.fetch_all(sql)

    def get_table_stats(self, table_name: str):
        sql = f"SELECT TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH, DATA_FREE, AUTO_INCREMENT" \
              f" FROM information_schema.TABLES WHERE table_name = '{table_name}' AND table_schema = DATABASE()"
        result = self.fetch_all(sql)
        return result[0] if result else {}

    def get_table_relationships(self, table_name: str):
        sql = f""" SELECT col.column_name AS from_column, ref.table_name AS to_table,
                          ref.column_name AS to_column
                   FROM information_schema.referential_constraints rc
                   JOIN information_schema.key_column_usage col
                     ON rc.constraint_name = col.constraint_name
                   AND rc.constraint_schema = col.constraint_schema
                   JOIN information_schema.key_column_usage ref
                     ON rc.unique_constraint_name = ref.constraint_name
                   AND rc.unique_constraint_schema = ref.constraint_schema
                   WHERE rc.constraint_schema = DATABASE()
                     AND rc.table_name = '{table_name}'
                """
        return self.fetch_all(sql)

    def rename_database(self, old_name: str, new_name: str):
        self.execute(f"ALTER DATABASE `{old_name}` RENAME TO `{new_name}`")

    def drop_database(self, db_name: str):
        self.ensure_not_default(db_name)
        self.execute(f"DROP DATABASE `{db_name}`")

    def rename_table(self, old_name: str, new_name: str):
        self.execute(f"RENAME TABLE `{old_name}` TO `{new_name}`")

    def drop_table(self, table_name: str):
        self.connection.cursor().execute(f"DROP TABLE IF EXISTS `{table_name}`")
        self.connection.commit()

    def save_dataframe_to_db(self, table_name: str, df, if_exists: str = "replace"):
        if if_exists == "replace":
            self.execute(f"DROP TABLE IF EXISTS `{table_name}`")
        if df.empty:
            return
        cols = DataProcessor.clean_column_names(list(df.columns))
        type_map = {
            "object": "TEXT",
            "int64": "BIGINT",
            "float64": "DOUBLE",
            "bool": "BOOLEAN",
            "datetime64[ns]": "DATETIME",
            "timedelta[ns]": "TIME",
        }
        field_types = [type_map.get(str(dt), "TEXT") for dt in df.dtypes]
        col_defs = ", ".join(f"`{c}` {t}" for c, t in zip(cols, field_types))
        self.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({col_defs})")
        # basic insert
        placeholders = ", ".join(["%s"] * len(cols))
        rows = [tuple(DataProcessor.sanitize_value(v) for v in row) for _, row in df.iterrows()]
        self.execute(f"INSERT INTO `{table_name}` (`{'` ,`'.join(cols)}`) VALUES ({placeholders})", rows)

    def ensure_not_default(self, name: str):
        pass


class PgExecutor(QueryExecutor):
    def get_tables(self):
        sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        rows = self.fetch_all(sql)
        return [r["table_name"] for r in rows]

    def get_table_info(self, table_name: str):
        sql = (f"SELECT column_name, data_type, is_nullable, column_default, ordinal_position"
               f" FROM information_schema.columns WHERE table_name = %s AND table_schema = 'public'")
        rows = self.fetch_all(sql, (table_name,))
        return [{
            "name": r["column_name"],
            "type": r["data_type"],
            "nullable": r["is_nullable"] == "YES",
            "default": r.get("column_default"),
            "pk": False,
            "fk": False,
        } for r in rows]

    def get_table_columns(self, table_name: str):
        return self.get_table_info(table_name)

    def get_table_indexes(self, table_name: str):
        sql = (f"SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s AND schemaname = 'public'")
        return self.fetch_all(sql, (table_name,))

    def get_table_stats(self, table_name: str):
        sql = (f"SELECT n_live_tup AS table_rows, pg_size_pretty(pg_total_relation_size(%s)) AS size",
               f" pg_total_relation_size(regclass(%s)) AS size_bytes FROM pg_stat_user_tables WHERE relname = %s")
        return self.fetch_all(sql, (table_name, table_name, table_name))

    def get_table_relationships(self, table_name: str):
        sql = (f"SELECT kcu.column_name AS from_column, ccu.table_name AS to_table,"
               f" ccu.column_name AS to_column"
               f" FROM information_schema.table_constraints tc"
               f" JOIN information_schema.key_column_usage kcu"
               f" ON tc.constraint_name = kcu.constraint_name"
               f" AND tc.table_schema = kcu.table_schema"
               f" JOIN information_schema.constraint_column_usage ccu"
               f" ON kcu.constraint_name = ccu.constraint_name"  
               f" WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s")
        return self.fetch_all(sql, (table_name,))

    def create_database(self, db_name: str):
        self.execute(f'CREATE DATABASE "{db_name}"')

    def get_procedure_list(self):
        sql = ("SELECT routine_name FROM information_schema.routines WHERE routine_type = 'PROCEDURE'"
               " AND routine_schema = 'public'")
        rows = self.fetch_all(sql)
        return [r["routine_name"] for r in rows]

    def delete_rows(self, table_name: str, where: str = None):
        sql = f"DELETE FROM {table_name}"
        if where:
            sql += f" WHERE {where}"
        return self.execute(sql)

    def update_rows(self, table_name: str, updates: dict, where: str = None):
        sql = f"UPDATE {table_name} SET " + ", ".join(f"{k} = %s" for k in updates)
        params = list(updates.values())
        if where:
            sql += f" WHERE {where}"
        return self.execute(sql, params)

    def insert_row(self, table_name: str, data: dict):
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
        return self.execute(sql, tuple(data.values()))
