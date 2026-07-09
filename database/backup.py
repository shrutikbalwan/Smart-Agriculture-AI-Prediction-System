"""
Database backup and restore utility.
Usage:
  python database/backup.py backup [output_file.sql]
  python database/backup.py restore [input_file.sql]
"""
import os
import sys
import subprocess
from datetime import datetime

DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = os.getenv("MYSQL_PORT", "3306")
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASS = os.getenv("MYSQL_PASSWORD", "")
DB_NAME = os.getenv("MYSQL_DATABASE", "smart_agriculture")


def backup(output_file=None):
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"backup_{DB_NAME}_{timestamp}.sql"

    os.makedirs("database/backups", exist_ok=True)
    output_path = os.path.join("database/backups", output_file)

    env = os.environ.copy()
    if DB_PASS:
        env["MYSQL_PWD"] = DB_PASS

    cmd = [
        "mysqldump",
        f"--host={DB_HOST}",
        f"--port={DB_PORT}",
        f"--user={DB_USER}",
        "--routines",
        "--triggers",
        "--single-transaction",
        DB_NAME,
    ]

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            result = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"Backup saved: {output_path}")
        else:
            print(f"Backup failed: {result.stderr}")
            sys.exit(1)
    except FileNotFoundError:
        print("mysqldump not found. Ensure MySQL tools are installed and in PATH.")
        sys.exit(1)


def restore(input_file):
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)

    env = os.environ.copy()
    if DB_PASS:
        env["MYSQL_PWD"] = DB_PASS

    cmd = [
        "mysql",
        f"--host={DB_HOST}",
        f"--port={DB_PORT}",
        f"--user={DB_USER}",
        DB_NAME,
    ]

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            result = subprocess.run(cmd, env=env, stdin=f, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"Restored from: {input_file}")
        else:
            print(f"Restore failed: {result.stderr}")
            sys.exit(1)
    except FileNotFoundError:
        print("mysql client not found. Ensure MySQL tools are installed and in PATH.")
        sys.exit(1)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python database/backup.py backup|restore [file]")
        sys.exit(1)

    command = sys.argv[1]
    file_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if command == "backup":
        backup(file_arg)
    elif command == "restore":
        restore(file_arg)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
