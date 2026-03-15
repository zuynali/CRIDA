import logging
import mysql.connector
from mysql.connector import pooling, Error

from config import Config

logger = logging.getLogger(__name__)

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
            autocommit=False  
        )
    return _pool


def get_connection():
    return get_pool().get_connection()


def execute_query(sql, params=None, fetch=False):

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


def execute_transaction(operations):

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


def execute_transaction_custom(fn):

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
    try:
        row = execute_query("SELECT 1 AS ok", fetch='one')
        return row and row.get('ok') == 1
    except Exception:
        return False
