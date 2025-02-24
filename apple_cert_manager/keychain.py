import subprocess
import env_config
import os
import tempfile
import requests

# ✅ Apple WWDR CA 憑證官方下載 URL
APPLE_WWDR_CA_URL = "https://www.apple.com/certificateauthority/AppleWWDRCAG3.cer"

def unlock_keychain():
    """🚀 使用 Fastlane 解鎖 macOS Keychain"""
    keychain_path = os.path.expanduser(env_config.keychain_path)
    keychain_password = env_config.keychain_password
    run_subprocess([
        "fastlane", "run", "unlock_keychain",
        f"path:{keychain_path}",
        f"password:{keychain_password}"
    ], "解鎖 Keychain")
        
def configure_keychain_search():
    """設定自訂 Keychain 為預設搜索範圍"""
    try:
        keychain_path = os.path.expanduser(env_config.keychain_path)
        run_subprocess(
            ["security", "list-keychains", "-s", keychain_path],
            "設置 Keychain 搜索範圍"
        )
        print(f"已設置 Keychain 搜索範圍為：{keychain_path}")
    except Exception as e:
        print(f"設置 Keychain 搜索範圍失敗：{e}")
        raise

def set_key_partition_list():
    """設定 Keychain 分區列表權限"""
    try:
        keychain_path = os.path.expanduser(env_config.keychain_path)
        keychain_password = env_config.keychain_password
        run_subprocess(
            ["security", "set-key-partition-list", "-S", "apple-tool:,apple:", "-k", keychain_password, keychain_path],
            "設置 Keychain 分區列表權限"
        )
        print(f"已設置分區列表權限：{keychain_path}")
    except Exception as e:
        print(f"設置分區列表權限失敗：{e}")
        
def restore_default_keychain(original_keychains):
    """恢復預設鑰匙圈"""
    if original_keychains:
        try:
            subprocess.run(
                ["security", "list-keychains", "-s"] + original_keychains,
                check=True
            )
            print(f"已恢復預設鑰匙圈：{original_keychains}")
        except Exception as e:
            print(f"恢復預設鑰匙圈失敗：{e}")
            
def debug_keychain_identities():
    """列出 Keychain 中的簽名身份"""
    try:
        keychain_path = os.path.expanduser(env_config.keychain_path)
        result = run_subprocess(
            ["security", "find-identity", "-p", "codesigning", keychain_path],
            "列出 Keychain 簽名身份",
            stdout=subprocess.PIPE,
        )
        print("Keychain 中的簽名身份：")
        print(result.stdout)
    except Exception as e:
        print(f"無法列出簽名身份：{e}")
        
def is_apple_wwdr_installed(keychain_path):
    """🔍 檢查 `AppleWWDRCA` 憑證是否已安裝"""
    result = subprocess.run(["security", "find-certificate", "-c", "Apple Worldwide Developer Relations", "-a", keychain_path],
        capture_output=True, text=True)
    return "Apple Worldwide Developer Relations" in result.stdout


def install_apple_wwdr_certificate():
    """🚀 免 `sudo` 安裝 `Apple WWDR CA` 到指定 Keychain"""
    # 1️⃣ 取得 Keychain 路徑
    keychain_path = os.path.expanduser(env_config.keychain_path)
    # 2️⃣ 檢查是否已安裝
    if is_apple_wwdr_installed(keychain_path):
        print(f"✅ `Apple WWDR CA` 憑證已安裝於 {keychain_path}，無需重新安裝")
        return True
    print(f"🔍 `Apple WWDR CA` 憑證未安裝於 {keychain_path}，正在下載...")
    try:
        # 3️⃣ 下載 `AppleWWDRCA` 憑證
        response = requests.get(APPLE_WWDR_CA_URL)
        if response.status_code != 200:
            print("❌ 無法下載 `Apple WWDR CA` 憑證")
            return False
        # 4️⃣ 保存到臨時檔案
        with tempfile.NamedTemporaryFile(delete=False, suffix=".cer") as temp_cer:
            temp_cer.write(response.content)
            temp_cer_path = temp_cer.name
        print(f"✅ 下載成功: {temp_cer_path}")
        # 5️⃣ 🚀 **使用 `security trust-settings-import` 免 `sudo`**
        print(f"🔍 安裝到 Keychain: {keychain_path}")
        run_subprocess(["security", "add-certificates", "-k", keychain_path, temp_cer_path],
            f"安裝 Apple WWDR CA 到 {keychain_path}")
        print(f"✅ `Apple WWDR CA` 安裝成功於 {keychain_path}！")
        # 6️⃣ 刪除臨時檔案
        os.remove(temp_cer_path)
        return True
    except Exception as e:
        print(f"❌ 安裝 `Apple WWDR CA` 失敗: {e}")
        return False
        
def run_subprocess(command, description):
    """🚀 執行 Shell 命令，並隱藏無用輸出"""
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 失敗: {e}")