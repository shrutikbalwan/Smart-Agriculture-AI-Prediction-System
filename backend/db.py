import os
import mysql.connector
from mysql.connector import Error

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "smart_agriculture")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))

db = None
cursor = None


def get_db():
    global db, cursor

    if db is not None and cursor is not None:
        return db, cursor

    try:
        db = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
        )
        cursor = db.cursor()
        print("✅ Database Connected Successfully")
        return db, cursor
    except Error as exc:
        print(f"⚠️ Database unavailable: {exc}")
        db = None
        cursor = None
        return None, None


def close_db():
    global db, cursor

    if cursor is not None:
        cursor.close()
        cursor = None

    if db is not None:
        db.close()
        db = None


if __name__ == "__main__":
    get_db()