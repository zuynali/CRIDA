"""
db.py — MySQL Connection Pool & ACID Transaction Helpers
=========================================================
All SQL uses %s placeholders — NEVER string concatenation.

Public API:
  get_connection()               → raw connection from pool
  execute_query(sql, params, fetch)  → SELECT / single DML helper
  execute_transaction(operations)    → list of (sql, params) — atomic
  execute_transaction_custom(fn)     → fn(conn, cursor) — flexible ACID
  test_connection()              → startup health check
"""

import logging
import mysql.connector
from mysql.connector import pooling, Error

from config import Config

logger = logging.getLogger(__name__)

# ── Connection pool (created once at startup) ──────────────────────────────
_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="crida_pool",
            pool_size=Config.DB_POOL_SIZE,
            pool_reset_session=True,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            autocommit=False  # We manage commits manually
        )
    return _pool


def get_connection():
    """Get a connection from the pool."""
    return get_pool().get_connection()


# ── Helper: run a single SELECT/DML with auto-commit ──────────────────────
def execute_query(sql, params=None, fetch=False):
    """
    Run a parameterised query.

    fetch=False      → DML (INSERT/UPDATE/DELETE) → commits, returns lastrowid
    fetch='one'      → SELECT single row           → returns dict or None
    fetch='all'      → SELECT all rows             → returns list of dicts
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        if fetch == 'one':
            return cursor.fetchone()
        elif fetch == 'all':
            return cursor.fetchall()
        else:
            conn.commit()
            return cursor.lastrowid
    except Error as e:
        conn.rollback()
        logger.error(f"execute_query error: {e} | SQL: {sql}")
        raise
    finally:
        cursor.close()
        conn.close()


# ── Helper: ACID transaction wrapper ─────────────────────────────────────
def execute_transaction(operations):
    """
    ACID transaction runner.

    operations: list of (sql_string, params_tuple) pairs.
    All succeed or all rollback (Atomicity guaranteed).
    Returns list of lastrowids in same order.

    Isolation level: READ COMMITTED
      → Prevents dirty reads.
      → Concurrent transactions cannot see uncommitted changes.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    results = []
    try:
        conn.start_transaction(isolation_level='READ COMMITTED')
        for sql, params in operations:
            cursor.execute(sql, params or ())
            results.append(cursor.lastrowid)
        conn.commit()
        logger.info(f"Transaction committed: {len(operations)} operations")
        return results
    except Error as e:
        conn.rollback()
        logger.error(f"Transaction ROLLED BACK: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


# ── Helper: custom transaction with callable steps ────────────────────────
def execute_transaction_custom(fn):
    """
    ACID transaction with arbitrary Python logic.

    fn(conn, cursor) is called inside BEGIN...COMMIT.
    Returns whatever fn returns.
    Any exception triggers automatic ROLLBACK.

    Usage:
        def my_ops(conn, cursor):
            cursor.execute("INSERT ...", (...))
            new_id = cursor.lastrowid
            cursor.execute("UPDATE ...", (new_id,))
            return new_id

        result = execute_transaction_custom(my_ops)
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction(isolation_level='READ COMMITTED')
        result = fn(conn, cursor)
        conn.commit()
        logger.info("Custom transaction committed")
        return result
    except Error as e:
        conn.rollback()
        logger.error(f"Custom transaction ROLLED BACK: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def test_connection():
    """Startup health check — returns True if DB is reachable."""
    try:
        row = execute_query("SELECT 1 AS ok", fetch='one')
        return row and row.get('ok') == 1
    except Exception:
        return False
