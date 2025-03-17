import jwt
import os
import logging
from apple_cert_manager.config import config 
from . import apple_accounts
from datetime import datetime, timedelta

logging = logging.getLogger(__name__)


def generate_token(apple_id):
    """ 生成 JWT Token 用於 App Store Connect API """
    account = apple_accounts.get_account_by_apple_id(apple_id)
    if not account:
        raise Exception(f"❌ 找不到 Apple ID: {apple_id} 的帳戶資訊")
    key_id = account['key_id']
    issuer_id = account['issuer_id']
    api_key_dir = config.api_key_dir_path  # 取得目錄
    private_key_path = os.path.join(api_key_dir, f"AuthKey_{key_id}.p8")  # 拼接完整路徑

    if not os.path.exists(private_key_path):
        raise Exception(f"API Key 檔案不存在: {private_key_path}，請檢查.env中API_KEY_DIR_PATH配置")

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
