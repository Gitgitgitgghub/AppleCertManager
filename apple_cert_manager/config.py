import os
from dotenv import load_dotenv

# 🚀 讀取 `.env`
load_dotenv()

class Config:
    """📌 直接從 `.env` 讀取變數，不重複拼接"""
    
    root_dir = os.getenv("ROOT_DIR")  # ✅ 讀取 `ROOT_DIR`
    
    api_key_dir_path = os.getenv("API_KEY_DIR_PATH")
    api_key_json_dir_path = os.getenv("API_KEY_JSON_DIR_PATH")
    db_path = os.getenv("DB_PATH")
    cert_dir_path = os.getenv("CERT_DIR_PATH")
    profile_dir_path = os.getenv("PROFILE_DIR_PATH")
    ipa_path = os.getenv("IPA_PATH")
    json_path = os.getenv("JSON_PATH")
    keychain_path = os.getenv("KEYCHAIN_PATH")
    keychain_password = os.getenv("KEYCHAIN_PASSWORD")  # 直接從 `.env` 讀取
    bundle_id = os.getenv("BUNDLE_ID")

# ✅ 讓 `config` 變數可用
config = Config()
