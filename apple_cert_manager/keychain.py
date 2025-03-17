import subprocess
from apple_cert_manager.config import config 
import os
import tempfile
import requests
import logging

logging = logging.getLogger(__name__)

# ✅ Apple WWDR CA 憑證官方下載 URL
APPLE_WWDR_CA_URL = "https://www.apple.com/certificateauthority/AppleWWDRCAG3.cer"

def unlock_keychain():
    """🚀 確保 Keychain 存在，然後解鎖"""
    keychain_path = os.path.expanduser(config.keychain_path)
    keychain_password = config.keychain_password

    try:
        # **🔍 檢查 Keychain 是否存在**
        if not os.path.exists(keychain_path):
            logging.info(f"⚠️ 找不到 Keychain: {keychain_path}，正在建立...")
            create_keychain(keychain_path, keychain_password)

        # **🔓 執行 `security unlock-keychain` 解鎖**
        run_subprocess([
            "security", "unlock-keychain", "-p", keychain_password, keychain_path
        ], "解鎖 Keychain")

        logging.info(f"✅ 成功解鎖 Keychain: {keychain_path}")

    except subprocess.CalledProcessError as e:
        raise Exception(f"❌ 解鎖 Keychain 失敗: {e}")
        
def create_keychain(keychain_path, keychain_password):
    """🛠 創建新的 Keychain 並設定為預設"""
    try:
        run_subprocess([
            "security", "create-keychain", "-p", keychain_password, keychain_path
        ], "建立新的 Keychain")
        # 🔍 取得當前系統的 Keychain 列表
        result = subprocess.run(
            ["security", "list-keychains"],
            stdout=subprocess.PIPE, text=True, check=True
        )
        existing_keychains = [
            keychain.strip().strip('"') for keychain in result.stdout.splitlines()
        ]
        # 如果 keychain 已經在列表中，則無需添加
        if keychain_path in existing_keychains:
            logging.info(f"✅ `{keychain_path}` 已經在 Keychain 搜尋列表內")
            return
        # 🚀 保留原始 keychains，並新增我們的 keychain（避免覆蓋）
        new_keychains = existing_keychains + [keychain_path]
        # 設定新的 Keychain 列表（確保不覆蓋）
        run_subprocess(["security", "list-keychains", "-s"] + new_keychains, "更新 Keychain 搜尋列表")
        logging.info(f"✅ 已成功建立並設置 Keychain: {keychain_path}")

    except subprocess.CalledProcessError as e:
        raise Exception(f"❌ 建立 Keychain 失敗: {e}")
        
def import_cert_to_keychain(private_key_path, cert_path):
    """將私鑰和憑證導入 macOS Keychain"""
    logging.info("🔐 將憑證和私鑰導入 Keychain...")
    try:
        unlock_keychain()
        keychain_path = os.path.expanduser(config.keychain_path)
        # 導入私鑰
        subprocess.run([
            "security", "import", private_key_path,
            "-k", keychain_path,
            "-T", "/usr/bin/codesign"  # 允許 codesign 訪問
        ], check=True)
        logging.info(f"✅ 私鑰已導入 Keychain: {private_key_path}")
        # 導入憑證
        subprocess.run([
            "security", "import", cert_path,
            "-k", keychain_path,
            "-T", "/usr/bin/codesign"
        ], check=True)
        logging.info(f"✅ 憑證已導入 Keychain: {cert_path}")

    except subprocess.CalledProcessError as e:
        raise Exception(f"❌ 導入 Keychain 失敗: {e}")
        
def configure_keychain_search():
    """設定自訂 Keychain 為預設搜索範圍"""
    try:
        keychain_path = os.path.expanduser(config.keychain_path)
        run_subprocess(
            ["security", "list-keychains", "-s", keychain_path],
            "設置 Keychain 搜索範圍"
        )
        logging.info(f"已設置 Keychain 搜索範圍為：{keychain_path}")
    except Exception as e:
        raise Exception(f"設置 Keychain 搜索範圍失敗：{e}")

def set_key_partition_list():
    """設定 Keychain 分區列表權限"""
    try:
        keychain_path = os.path.expanduser(config.keychain_path)
        keychain_password = config.keychain_password
        run_subprocess(
            ["security", "set-key-partition-list", "-S", "apple-tool:,apple:", "-k", keychain_password, keychain_path],
            "設置 Keychain 分區列表權限"
        )
        logging.info(f"已設置分區列表權限：{keychain_path}")
    except Exception as e:
        raise Exception(f"設置分區列表權限失敗：{e}")
        
def restore_default_keychain(original_keychains):
    """恢復預設鑰匙圈"""
    if original_keychains:
        try:
            subprocess.run(
                ["security", "list-keychains", "-s"] + original_keychains,
                check=True
            )
            logging.info(f"已恢復預設鑰匙圈：{original_keychains}")
        except Exception as e:
            raise Exception(f"恢復預設鑰匙圈失敗：{e}")
            
def debug_keychain_identities():
    """列出 Keychain 中的簽名身份"""
    try:
        keychain_path = os.path.expanduser(config.keychain_path)
        result = run_subprocess(
            ["security", "find-identity", "-p", "codesigning", keychain_path],
            "列出 Keychain 簽名身份",
            stdout=subprocess.PIPE,
        )
        logging.info("Keychain 中的簽名身份：")
        logging.info(result.stdout)
    except Exception as e:
        logging.error(f"無法列出簽名身份：{e}")
        
def is_apple_wwdr_installed(keychain_path):
    """🔍 檢查 `AppleWWDRCA` 憑證是否已安裝"""
    result = subprocess.run(["security", "find-certificate", "-c", "Apple Worldwide Developer Relations", "-a", keychain_path],
        capture_output=True, text=True)
    return "Apple Worldwide Developer Relations" in result.stdout


def install_apple_wwdr_certificate():
    """🚀 免 `sudo` 安裝 `Apple WWDR CA` 到指定 Keychain"""
    # 1️⃣ 取得 Keychain 路徑
    keychain_path = os.path.expanduser(config.keychain_path)
    # 2️⃣ 檢查是否已安裝
    if is_apple_wwdr_installed(keychain_path):
        print(f"✅ `Apple WWDR CA` 憑證已安裝於 {keychain_path}，無需重新安裝")
        return True
    logging.info(f"🔍 `Apple WWDR CA` 憑證未安裝於 {keychain_path}，正在下載...")
    try:
        # 3️⃣ 下載 `AppleWWDRCA` 憑證
        response = requests.get(APPLE_WWDR_CA_URL)
        if response.status_code != 200:
            raise Exception("❌ 無法下載 `Apple WWDR CA` 憑證")
        # 4️⃣ 保存到臨時檔案
        with tempfile.NamedTemporaryFile(delete=False, suffix=".cer") as temp_cer:
            temp_cer.write(response.content)
            temp_cer_path = temp_cer.name
        logging.info(f"✅ 下載成功: {temp_cer_path}")
        # 5️⃣ 🚀 **使用 `security trust-settings-import` 免 `sudo`**
        logging.info(f"🔍 安裝到 Keychain: {keychain_path}")
        run_subprocess(["security", "add-certificates", "-k", keychain_path, temp_cer_path],
            f"安裝 Apple WWDR CA 到 {keychain_path}")
        logging.info(f"✅ `Apple WWDR CA` 安裝成功於 {keychain_path}！")
        # 6️⃣ 刪除臨時檔案
        os.remove(temp_cer_path)
    except Exception as e:
        raise Exception(f"❌ 安裝 `Apple WWDR CA` 失敗: {e}")
        
def run_subprocess(command, description):
    """🚀 執行 Shell 命令，並在失敗時拋出異常"""
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        raise Exception(f"❌ {description} 失敗: {e.stderr.strip() or str(e)}")