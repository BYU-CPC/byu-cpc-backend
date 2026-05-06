from contextlib import contextmanager

import psycopg2
from psycopg2 import pool

from environment import DATABASE_URL


_connection_pool = pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)


@contextmanager
def get_db():
    """
    Yield a database cursor inside a transaction.

    Each caller gets a connection from the pool. Successful blocks are committed;
    failed blocks are rolled back so the connection is safe to reuse. The cursor is
    always closed and the connection is always returned to the pool.
    """
    connection = _connection_pool.getconn()
    cursor = connection.cursor()
    try:
        yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        _connection_pool.putconn(connection)
