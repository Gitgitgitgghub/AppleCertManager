import sqlite3
import os
import json
import sys
import concurrent.futures
from . import match
from . import local_file
from . import certificate
from . import database
from apple_cert_manager.config import config
from datetime import datetime
from functools import wraps

# ✅ 確保資料庫只初始化一次
DATABASE_INITIALIZED = False

def initialize_database():
    """ 確保 SQLite 資料庫存在 """
    global DATABASE_INITIALIZED
    if DATABASE_INITIALIZED:
        return  # ✅ 已初始化，直接返回

    if not os.path.exists(config.db_path):
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
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row  # ✅ 讓 cursor.fetchall() 回傳 dict-like 物件
    cursor = conn.cursor()

    cursor.execute("SELECT apple_id, issuer_id, key_id, cert_id, created_at FROM accounts")
    accounts = cursor.fetchall()  # 🚀 這樣回傳的是 `sqlite3.Row`，可以用 key 存取

    conn.close()
    return accounts

@ensure_database_initialized
def get_account_by_apple_id(apple_id):
    """ 透過 Apple ID 取得帳號資訊 """
    conn = sqlite3.connect(config.db_path)
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
        conn = sqlite3.connect(config.db_path)
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
    conn = sqlite3.connect(config.db_path)
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
    conn = sqlite3.connect(config.db_path)
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
        

def insert_from_json(json_path=None):
    """ 🚀 從 JSON 批量插入 Apple 帳號（不覆蓋現有帳號），插入後並行執行 match.match_apple_account """

    json_path = json_path or config.JSON_PATH  # ✅ 預設 JSON 檔案
    if not os.path.exists(json_path):
        print(f"❌ 找不到 JSON 檔案: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as file:
        try:
            accounts = json.load(file)
            if not isinstance(accounts, list):
                print("❌ JSON 格式錯誤，應該是陣列")
                return

            # 🚀 使用 ThreadPoolExecutor 來並行插入帳號
            with concurrent.futures.ThreadPoolExecutor() as executor:
                list(executor.map(lambda acc: insert_account(
                    acc.get("apple_id"),
                    acc.get("issuer_id"),
                    acc.get("key_id")
                ), accounts))
        except json.JSONDecodeError:
            print("❌ JSON 解析錯誤")


@ensure_database_initialized
def delete_account(apple_id):
    """ 刪除指定 Apple ID，並刪除相關的 `.cer` 和 `.mobileprovision` 檔案 """
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()

    # ✅ 先獲取 `cert_id`
    cursor.execute("SELECT cert_id, key_id FROM accounts WHERE apple_id = ?", (apple_id,))
    row = cursor.fetchone()

    if not row:
        print(f"⚠️ Apple ID {apple_id} 不存在，無法刪除")
        conn.close()
        return False

    cert_id = row[0]  # 取得 `cert_id`
    # ✅ 如果 `cert_id` 存在，則刪除本地憑證檔案
    if cert_id:
        certificate.remove_keychain_certificate_by_id(cert_id)
        local_file.remove_local_files(apple_id)
    # ✅ 刪除帳號
    cursor.execute("DELETE FROM accounts WHERE apple_id = ?", (apple_id,))
    conn.commit()
    conn.close()
    print(f"✅ 已刪除 Apple ID: {apple_id}")

    
    return True
    
@ensure_database_initialized
def query_accounts():
    """ 查詢所有 Apple 帳號 """
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT apple_id, issuer_id, key_id, cert_id, created_at FROM accounts")
    accounts = cursor.fetchall()
    conn.close()

    if not accounts:
        print("⚠️ 沒有任何帳戶資料")
    else:
        for account in accounts:
            print(f"📜 Apple ID: {account[0]}, Issuer ID: {account[1]}, Key ID: {account[2]}, Cert ID: {account[3] or '❌ 無憑證'}, Created At: {account[4] or 'N/A'}")


