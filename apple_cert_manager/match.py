from . import apple_accounts
from . import certificate
from . import profile
from . import local_file
from apple_cert_manager.config import config
import logging
import os

logging = logging.getLogger(__name__)

def match_apple_account(apple_id):
    """ 設定這個apple帳號的憑證與profile """
    account = apple_accounts.get_account_by_apple_id(apple_id)
    logging.info(f"🔍 開始設定 Apple ID: {apple_id} 憑證與profile")
    try:
        if not account:
            raise Exception(f"❌ 找不到 Apple ID，無法取得憑證")
        cert_id = account['cert_id']
        cert_file_path = os.path.join(config.cert_dir_path, f"{cert_id}.cer")
        # 檢查憑證id與憑證檔案是否存在 不存在則創建新的
        if not cert_id or not os.path.exists(cert_file_path):
            cert_id = certificate.create_certificate(apple_id)
            if cert_id:
                apple_accounts.update_cert_id(apple_id, cert_id)
                logging.info(f"✅ 已建立帳號: {apple_id} 新的憑證✅")
            else:
                raise Exception(f"❌憑證建立失敗")
        # 更新 profile
        profile.get_provisioning_profile(apple_id)
        logging.info(f"✅ 已建立帳號: {apple_id} 新的憑證與profile檔案✅")
    except Exception as e:
        raise Exception(f"match_apple_account : {apple_id} 錯誤: {e}")