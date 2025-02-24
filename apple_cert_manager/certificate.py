import subprocess
import os
import tempfile
import auth
import re
import requests
import base64
import hashlib
import apple_accounts
import env_config
import keychain
from datetime import datetime

def create_distribution_certificate(apple_id):
    """ 用 Fastlane `cert` 來建立新的 iOS Distribution 憑證 """
    keychain_path = env_config.keychain_path
    keychain_password = env_config.keychain_password
    cert_output_path = env_config.cert_dir_path
    # **🚀 產生 Fastlane API Key JSON**
    api_key_json_path = auth.generate_fastlane_api_key_json(apple_id)
    if not api_key_json_path:
        print("❌ 產生 API Key JSON 失敗，無法繼續建立憑證")
        return False
    try:
        # **🚀 呼叫 Fastlane `cert` 來建立 Distribution 憑證**
        result = subprocess.run(
            [
                "fastlane", "run", "cert",
                "development", "false",  # 建立 Distribution 憑證
                f"api_key_path:{api_key_json_path}",  # ✅ 傳入 Fastlane API Key JSON
                f"output_path:{cert_output_path}",
                f"keychain_path:{keychain_path}",
                f"keychain_password:{keychain_password}",
                "force:true"  # ✅ 強制建立新憑證
            ],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # 🚀 解析 `Result:` 後面的憑證 ID
            stdout = result.stdout  # Fastlane 輸出
            match = re.search(r"Result:\s*([A-Za-z0-9]+)", stdout)
            if match:
                certificate_id = match.group(1)
                print(f"✅ 成功建立新的 iOS Distribution 憑證 ID: {certificate_id}")
                return certificate_id  # ✅ 回傳憑證 ID
            else:
                print("❌ 未找到憑證 ID")
                print("📌 Fastlane 輸出：")
                print(stdout)
                return None
        else:
            print(f"❌ 建立憑證失敗: {result.stderr}")
            return None

    except Exception as e:
        print(f"❌ Fastlane 無法建立憑證: {e}")
        return None
        
def revoke_certificate(apple_id, cert_id):
    """ 從 App Store Connect 刪除指定憑證 """
    token = auth.generate_token(apple_id)
    url = f"https://api.appstoreconnect.apple.com/v1/certificates/{cert_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    response = requests.delete(url, headers=headers)
    if response.status_code == 204:
        print(f"成功刪除遠端憑證 ID: {cert_id}")
        return True
    else:
        print(f"刪除憑證失敗: {response.status_code} - {response.text}")
        return False
        
def revoke_oldest_distribution_certificate(apple_id):
    """ 如果 `DISTRIBUTION` 類型憑證超過 2 個，則刪除最早過期的 """
    account = apple_accounts.get_account_by_apple_id(apple_id)
    if not account:
        print(f"❌ 找不到 Apple ID: {apple_id} 的帳戶資訊")
        return None
    issuer_id = account['issuer_id']
    key_id = account['key_id']
    all_certs = list_certificates(apple_id)
    distribution_certs = filter_distribution_certificates(all_certs)

    if len(distribution_certs) >= 2:
        # ✅ 取出最早過期的憑證
        distribution_certs.sort(key=lambda cert: cert['attributes']["expirationDate"])
        cert_to_remove = distribution_certs[0]
        cert_id = cert_to_remove["id"]
        cert_name = cert_to_remove['attributes']["name"]
        expiration_date = cert_to_remove['attributes']["expirationDate"]

        print(f"⚠️ `DISTRIBUTION` 類型憑證超過 2 個，準備刪除最早過期的憑證:")
        print(f"  - 憑證名稱: {cert_name}")
        print(f"  - 憑證 ID: {cert_id}")
        print(f"  - 到期日: {expiration_date}")

        # 🚀 刪除憑證
        if revoke_certificate(apple_id, cert_id):
            print(f"✅ 成功刪除最早過期的憑證: {cert_name} ({cert_id})")
            return cert_id
        else:
            print(f"❌ 無法刪除憑證: {cert_name} ({cert_id})")
            return None
    else:
        print("✅ `DISTRIBUTION` 憑證數量符合規範，不需要刪除")
        return None
        
def format_expiration_date(expiration):
    """ 格式化日期 """
    try:
        exp_date = datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%S.%f%z")
        return exp_date.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Invalid date"
        
def list_certificates(apple_id):
    """ 列出 App Store Connect 上的憑證 """
    token = auth.generate_token(apple_id)
    url = "https://api.appstoreconnect.apple.com/v1/certificates"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        certificates = response.json()["data"]
        for cert in certificates:
            print(f"憑證ID: {cert['id']}, 名稱: {cert['attributes']['name']} 類型: {cert['attributes']['certificateType']} 到期日期: {format_expiration_date(cert['attributes']['expirationDate'])}")
        return certificates
    else:
        print(f"獲取憑證失敗: {response.status_code} - {response.text}")
        return None
    
def filter_distribution_certificates(certificates):
    """ 過濾 `DISTRIBUTION` 和 `IOS_DISTRIBUTION` 類型的憑證 """
    return [
        cert for cert in certificates if cert['attributes']['certificateType'] in ["DISTRIBUTION", "IOS_DISTRIBUTION"]
    ]

def find_private_key(cert_name):
    """ 搜尋私鑰 """
    keychain_path = os.path.expanduser(env_config.keychain_path)
    search_command = ["security", "find-identity", "-v", "-p", "codesigning", keychain_path]
    result = subprocess.run(search_command, capture_output=True, text=True)
    
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            if cert_name in line:
                import re
                matches = re.findall(r'([A-F0-9]{40})', line, re.IGNORECASE)
                if matches:
                    return matches[0]
    return None

def get_cert_name_from_file(cert_file_path):
    """ 🔍 從 `.cert` 檔案讀取憑證名稱 (Common Name) 並去除 Team ID """
    if not os.path.exists(cert_file_path):
        print(f"❌ 憑證檔案不存在: {cert_file_path}")
        return None
    print(f"🔍 正在解析憑證檔案: {cert_file_path}")
    # ✅ 讀取憑證名稱 (Common Name)
    get_cert_name_command = ["openssl", "x509", "-noout", "-subject", "-in", cert_file_path]
    result = subprocess.run(get_cert_name_command, capture_output=True, text=True)
    common_name_match = re.search(r"CN\s?=\s?([^,]+)", result.stdout)
    cert_name = common_name_match.group(1).strip() if common_name_match else None
    if cert_name:
        cert_name = re.sub(r"\s*\(.*?\)$", "", cert_name)
    return cert_name

def remove_keychain_certificate(cert):
    """ 從 macOS Keychain 刪除指定的憑證與私鑰，如果有apple portal 的cert資料用這個 """
    keychain.unlock_keychain()
    cert_name = cert['attributes']['name']
    keychain_path = os.path.expanduser(env_config.keychain_path)
    print(f"🔍 正在刪除 {cert_name}")
    key_hash = find_private_key(cert_name)
    if key_hash:
        try:
            delete_identity_command = ["security", "delete-identity", "-Z", key_hash, keychain_path]
            subprocess.run(delete_identity_command, check=True)
            print(f"✅ 成功刪除私鑰和相關聯的憑證")
        except subprocess.CalledProcessError:
            print(f"❌ 刪除私鑰失敗")
    else:
        print("❌ 未找到私鑰")

def remove_keychain_certificate_by_id(cert_id):
    """ 🚀 透過 `cert_id` 刪除 macOS Keychain 中的憑證與私鑰 """
    keychain.unlock_keychain()
    keychain_path = keychain_path = os.path.expanduser(env_config.keychain_path)
    cert_file_path = os.path.join(env_config.cert_dir_path, f"{cert_id}.cer")
    # 解析 `.cert` 取得憑證名稱
    cert_name = get_cert_name_from_file(cert_file_path)
    if not cert_name:
        print("❌ 無法從 `.cert` 檔案讀取憑證名稱，請確認檔案內容是否正確")
        return
    print(f"🔍 正在刪除 `{cert_name}` 及相關的私鑰...")
    key_hash = find_private_key(cert_name)
    if key_hash:
        try:
            delete_identity_command = ["security", "delete-identity", "-Z", key_hash, keychain_path]
            subprocess.run(delete_identity_command, check=True)
            print(f"✅ 成功刪除私鑰和相關聯的憑證")
        except subprocess.CalledProcessError:
            print(f"❌ 刪除私鑰失敗")
    else:
        print("❌ 未找到私鑰")

    

