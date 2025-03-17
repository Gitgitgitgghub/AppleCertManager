import os
import logging
from apple_cert_manager.config import config 
from . import apple_accounts

logging = logging.getLogger(__name__)

def remove_local_files(cert_id):
    """ 刪除與 `cert_id` 相關的 `.cer` 和 `.mobileprovision` 檔案 """
    # ✅ 設定檔案路徑
    cert_dir_path = os.path.expanduser(config.cert_dir_path)  # `.cer` 檔案路徑
    profile_dir_path = os.path.expanduser(config.profile_dir_path)  # `.mobileprovision` 檔案路徑
    cer_file = os.path.join(cert_dir_path, f"{cert_id}.cer")
    mobile_provision_file = os.path.join(profile_dir_path, f"adhoc_{cert_id}.mobileprovision")
    # ✅ 刪除 `.cer` 文件
    if os.path.exists(cer_file):
        os.remove(cer_file)
        logging.info(f"✅ 成功刪除 `.cer` 文件: {cer_file}")
    else:
        logging.warning(f"⚠️ `.cer` 文件不存在: {cer_file}")

    # ✅ 刪除 `.mobileprovision` 文件
    if os.path.exists(mobile_provision_file):
        os.remove(mobile_provision_file)
        logging.info(f"✅ 成功刪除 `.mobileprovision` 文件: {mobile_provision_file}")
    else:
        logging.warning(f"⚠️ `.mobileprovision` 文件不存在: {mobile_provision_file}")

    return True
