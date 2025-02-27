import sqlite3
from apple_cert_manager.config import config 
import os

def initialize_database():
    """ 初始化 SQLite 資料庫，建立 accounts 表格，包含 cert_id """
    db_path = config.db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)  # ✅ 確保資料夾存在

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ✅ 建立 `accounts` 表格
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apple_id TEXT UNIQUE NOT NULL,
        issuer_id TEXT NOT NULL,
        key_id TEXT NOT NULL,
        cert_id TEXT DEFAULT NULL,  -- 允許 NULL（表示還沒建立憑證）
        created_at TIMESTAMP DEFAULT NULL  -- 憑證建立時間（NULL 代表尚未建立）
    )
    """)

    conn.commit()
    conn.close()
    print(f"✅ SQLite 資料庫已初始化: {db_path}")

# 🚀 執行初始化
if __name__ == "__main__":
    initialize_database()
