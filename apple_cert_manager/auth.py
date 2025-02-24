import jwt
import os
import json
import env_config
import apple_accounts
from datetime import datetime, timedelta


def generate_token(apple_id):
    """ 生成 JWT Token 用於 App Store Connect API """
    account = apple_accounts.get_account_by_apple_id(apple_id)
    if not account:
        print(f"❌ 找不到 Apple ID: {apple_id} 的帳戶資訊")
        return None
    key_id = account['key_id']
    issuer_id = account['issuer_id']
    api_key_dir = env_config.api_key_dir_path  # 取得目錄
    private_key_path = os.path.join(api_key_dir, f"AuthKey_{key_id}.p8")  # 拼接完整路徑

    if not os.path.exists(private_key_path):
        raise FileNotFoundError(f"API Key 檔案不存在: {private_key_path}")

    with open(private_key_path, "r") as f:
        private_key = f.read()

    payload = {
        "iss": issuer_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=20),
        "aud": "appstoreconnect-v1",
    }
    headers = {
        "alg": "ES256",
        "kid": key_id,
        "typ": "JWT",
    }

    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
    return token

def generate_fastlane_api_key_json(apple_id):
    """ 🚀 自動查詢 SQLite 取得 `key_id` & `issuer_id`，並產生 Fastlane API Key JSON """
    
    # 從 SQLite 查詢 `key_id` & `issuer_id`
    account = apple_accounts.get_account_by_apple_id(apple_id)
    if not account:
        print(f"❌ 找不到 Apple ID: {apple_id} 的帳戶資訊")
        return None
    key_id = account['key_id']
    issuer_id = account['issuer_id']

    # 取得 API Key JSON 存放路徑
    api_key_json_dir = os.path.expanduser(env_config.api_key_json_dir_path)
    os.makedirs(api_key_json_dir, exist_ok=True)  # ✅ 確保目錄存在

    json_file_path = os.path.join(api_key_json_dir, f"{key_id}.json")

    # 如果 JSON 已存在，直接回傳
    if os.path.exists(json_file_path):
        return json_file_path

    # 確保 .p8 檔案存在
    p8_file_path = os.path.join(env_config.api_key_dir_path, f"AuthKey_{key_id}.p8")
    if not os.path.exists(p8_file_path):
        print(f"❌ 找不到 .p8 檔案: {p8_file_path}")
        return None

    # 讀取 .p8 私鑰內容
    with open(p8_file_path, "r") as p8_file:
        private_key = p8_file.read().strip()

    # 生成 JSON 結構
    api_key_data = {
        "key_id": key_id,
        "issuer_id": issuer_id,
        "key": private_key,  # 🔹 把 .p8 內容存入 JSON
        "duration": 500,
        "in_house": False
    }

    # 產生 JSON 檔案
    with open(json_file_path, "w") as json_file:
        json.dump(api_key_data, json_file, indent=4)

    print(f"✅ Fastlane API Key JSON 已儲存: {json_file_path}")
    return json_file_path  
