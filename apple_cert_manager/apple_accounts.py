import sqlite3
import os
import env_config
import json
import sys
import match
import local_file
import certificate
import database
from datetime import datetime
from functools import wraps

DB_PATH = env_config.db_path

# ✅ 確保資料庫只初始化一次
DATABASE_INITIALIZED = False

def initialize_database():
    """ 確保 SQLite 資料庫存在 """
    global DATABASE_INITIALIZED
    if DATABASE_INITIALIZED:
        return  # ✅ 已初始化，直接返回

    if not os.path.exists(DB_PATH):
        database.initialize_database()
    
    DATABASE_INITIALIZED = True  # ✅ 設定為已初始化

def ensure_database_initialized(func):
    """ 裝飾器：確保執行資料庫操作前已初始化 """
    @wraps(func)
    def wrapper(*args, **kwargs):
        initialize_database()
        return func(*args, **kwargs)
    return wrapper

@ensure_database_initialized
def get_accounts():
    """ 取得所有 Apple 開發者帳號與憑證資訊 """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # ✅ 讓 cursor.fetchall() 回傳 dict-like 物件
    cursor = conn.cursor()

    cursor.execute("SELECT apple_id, issuer_id, key_id, cert_id, created_at FROM accounts")
    accounts = cursor.fetchall()  # 🚀 這樣回傳的是 `sqlite3.Row`，可以用 key 存取

    conn.close()
    return accounts

@ensure_database_initialized
def get_account_by_apple_id(apple_id):
    """ 透過 Apple ID 取得帳號資訊 """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # ✅ 讓回傳結果支援 dict-like 存取
    cursor = conn.cursor()

    cursor.execute("SELECT apple_id, issuer_id, key_id, cert_id, created_at FROM accounts WHERE apple_id = ?", (apple_id,))
    account = cursor.fetchone()

    conn.close()

    if account:
        return account
    else:
        print(f"⚠️ 找不到 Apple ID: {apple_id}")
        return None

@ensure_database_initialized
def insert_account(apple_id, issuer_id, key_id):
    """ 🚀 插入 Apple 開發者帳號，如果已存在則跳過 """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 🔍 檢查 `apple_id` 是否已存在
        cursor.execute("SELECT 1 FROM accounts WHERE apple_id = ?", (apple_id,))
        if cursor.fetchone():
            print(f"⚠️ Apple ID `{apple_id}` 已存在，跳過插入")
            conn.close()
            return False  # ✅ 已存在則跳過

        # ✅ 插入新的帳號 (`created_at` 為 NULL)
        cursor.execute("""
        INSERT INTO accounts (apple_id, issuer_id, key_id, created_at)
        VALUES (?, ?, ?, NULL)
        """, (apple_id, issuer_id, key_id))

        conn.commit()
        conn.close()
        print(f"✅ 新增 Apple ID `{apple_id}` 成功")
        match.match_apple_account(apple_id)
        return True  # ✅ 插入成功

    except sqlite3.Error as e:
        print(f"❌ 插入 Apple ID `{apple_id}` 失敗: {e}")
        return False
        
@ensure_database_initialized
def update_cert_id(apple_id, cert_id):
    """ 只更新 `cert_id`，並同步更新 `created_at` """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ✅ 先確認 `apple_id` 是否存在
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE apple_id = ?", (apple_id,))
    count = cursor.fetchone()[0]

    if count == 0:
        print(f"⚠️ Apple ID {apple_id} 不存在，無法更新 cert_id")
        conn.close()
        return False

    # 🚀 執行更新
    cursor.execute("""
        UPDATE accounts 
        SET cert_id = ?, created_at = ?
        WHERE apple_id = ?
    """, (cert_id, datetime.now(), apple_id))

    conn.commit()
    conn.close()
    print(f"✅ Apple ID {apple_id} 的 cert_id 更新為 {cert_id}")
    return True

@ensure_database_initialized
def clear_cert_id(apple_id):
    """ 將 `cert_id` 設為 NULL，並刪除相關的 `.cer` 和 `.mobileprovision` 檔案 """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # ✅ 先獲取 `cert_id`
    cursor.execute("SELECT cert_id FROM accounts WHERE apple_id = ?", (apple_id,))
    row = cursor.fetchone()

    if not row:
        print(f"⚠️ Apple ID {apple_id} 不存在，無法清除 cert_id")
        conn.close()
        return False

    cert_id = row[0]  # 取得 `cert_id`

    # ✅ 將 `cert_id` 設為 `NULL`
    cursor.execute("""
        UPDATE accounts 
        SET cert_id = NULL, created_at = ?
        WHERE apple_id = ?
    """, (datetime.now(), apple_id))

    conn.commit()
    conn.close()
    print(f"✅ Apple ID {apple_id} 的 cert_id 已清除")
    return True
        

@ensure_database_initialized
def insert_from_json(json_path=None):
    """ 從 JSON 批量插入 Apple 帳號（但不覆蓋現有帳號） """
    json_path = json_path or env_config.json_path  # ✅ 預設 JSON 檔案
    if not os.path.exists(json_path):
        print(f"❌ 找不到 JSON 檔案: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as file:
        try:
            accounts = json.load(file)

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            for account in accounts:
                apple_id = account.get("apple_id")
                issuer_id = account.get("issuer_id")
                key_id = account.get("key_id")
                cert_id = account.get("cert_id", None)

                # ✅ 先檢查 `apple_id` 是否已存在，因為怕忘記刪除舊有的json資料會把資料複寫掉
                cursor.execute("SELECT COUNT(*) FROM accounts WHERE apple_id = ?", (apple_id,))
                count = cursor.fetchone()[0]

                if count > 0:
                    print(f"⚠️ Apple ID {apple_id} 已存在，跳過導入")
                else:
                    # ✅ 只插入新 Apple ID，不覆蓋舊的
                    cursor.execute("""
                    INSERT INTO accounts (apple_id, issuer_id, key_id, cert_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """, (apple_id, issuer_id, key_id, cert_id, datetime.now() if cert_id else None))

                    print(f"✅ 新增 Apple ID: {apple_id}")

            conn.commit()
            conn.close()

        except json.JSONDecodeError:
            print("❌ JSON 格式錯誤")

@ensure_database_initialized
def delete_account(apple_id):
    """ 刪除指定 Apple ID，並刪除相關的 `.cer` 和 `.mobileprovision` 檔案 """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ✅ 先獲取 `cert_id`
    cursor.execute("SELECT cert_id, key_id FROM accounts WHERE apple_id = ?", (apple_id,))
    row = cursor.fetchone()

    if not row:
        print(f"⚠️ Apple ID {apple_id} 不存在，無法刪除")
        conn.close()
        return False

    cert_id = row[0]  # 取得 `cert_id`
    key_id = row[1]
    # ✅ 刪除帳號
    cursor.execute("DELETE FROM accounts WHERE apple_id = ?", (apple_id,))
    conn.commit()
    conn.close()
    print(f"✅ 已刪除 Apple ID: {apple_id}")

    # ✅ 如果 `cert_id` 存在，則刪除本地憑證檔案
    if cert_id:
        certificate.remove_keychain_certificate_by_id(cert_id)
        local_file.remove_local_files(cert_id)
    if key_id:
        local_file.remove_api_key_json(key_id)
    return True
    
@ensure_database_initialized
def query_accounts():
    """ 查詢所有 Apple 帳號 """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT apple_id, issuer_id, key_id, cert_id, created_at FROM accounts")
    accounts = cursor.fetchall()
    conn.close()

    if not accounts:
        print("⚠️ 沒有任何帳戶資料")
    else:
        for account in accounts:
            print(f"📜 Apple ID: {account[0]}, Issuer ID: {account[1]}, Key ID: {account[2]}, Cert ID: {account[3] or '❌ 無憑證'}, Created At: {account[4] or 'N/A'}")
        
# 🚀 CLI 入口
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ 錯誤：請提供指令，例如：")
        print("  python3 apple_accounts.py insert <apple_id> <issuer_id> <key_id>")
        print("  python3 apple_accounts.py delete <apple_id>")
        print("  python3 apple_accounts.py query")
        print("  python3 apple_accounts.py import accounts.json")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "insert" and len(sys.argv) == 5:
        insert_account(sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == "delete" and len(sys.argv) == 3:
        delete_account(sys.argv[2])
    elif command == "query":
        query_accounts()
    elif command == "import":
        json_path = sys.argv[2] if len(sys.argv) > 2 else None
        insert_from_json(json_path)
    else:
        print("❌ 無效的指令，請參考以下用法：")
        print("  python3 apple_accounts.py insert <apple_id> <issuer_id> <key_id>")
        print("  python3 apple_accounts.py delete <apple_id>")
        print("  python3 apple_accounts.py query")
        print("  python3 apple_accounts.py import [json_path]")
        sys.exit(1)


