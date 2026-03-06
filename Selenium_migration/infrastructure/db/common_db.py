import psycopg2
from psycopg2.extras import DictCursor
import os
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# Получаем параметры подключения к базе данных
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

DB_PARAMS = {
    'host': DB_HOST,
    'dbname': DB_NAME,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'port': DB_PORT
}


@contextmanager
def get_connection():
    """
    Контекстный менеджер для подключения к PostgreSQL.
    Пример:
        with get_connection() as conn:
            ...
    """
    print("[trace] get_connection start")
    conn = psycopg2.connect(**DB_PARAMS, cursor_factory=DictCursor)
    try:
        print("[trace] get_connection yield connection")
        yield conn
    finally:
        print("[trace] get_connection closing connection")
        conn.close()
