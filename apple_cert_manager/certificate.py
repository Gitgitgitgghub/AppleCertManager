import subprocess
import os
from . import auth
import re
import requests
import hashlib
import base64
from . import apple_accounts
from . import local_file
from apple_cert_manager.config import config 
from . import keychain
from datetime import datetime
        
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
    keychain_path = os.path.expanduser(config.keychain_path)
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

def get_cer_sha1(cert_id):
    """計算 `.cer` 檔案的 SHA-1 哈希值"""
    cert_file_path = os.path.join(config.cert_dir_path, f"{cert_id}.cer")
    if not os.path.exists(cert_file_path):
        print(f"❌ 檔案不存在: {cert_file_path}")
        return None
    sha1 = hashlib.sha1()
    try:
        with open(cert_file_path, "rb") as f:
            while chunk := f.read(4096):  # 讀取 4KB 區塊
                sha1.update(chunk)

        return sha1.hexdigest().upper()  # 轉大寫與 Apple 格式一致

    except Exception as e:
        print(f"❌ 無法計算 SHA-1: {e}")
        return None

def remove_keychain_certificate(cert):
    """ 從 macOS Keychain 刪除指定的憑證與私鑰，如果有apple portal 的cert資料用這個 """
    keychain.unlock_keychain()
    cert_name = cert['attributes']['name']
    keychain_path = os.path.expanduser(config.keychain_path)
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
    keychain_path = os.path.expanduser(config.keychain_path)
    cert_file_path = os.path.join(config.cert_dir_path, f"{cert_id}.cer")
    # 解析 `.cer` 取得憑證名稱
    cert_name = get_cert_name_from_file(cert_file_path)
    if not cert_name:
        print("❌ 無法從 `.cer` 檔案讀取憑證名稱，請確認檔案內容是否正確")
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

def generate_csr(apple_id, csr_path, private_key_path):
    """使用 OpenSSL 生成 CSR (憑證請求) 和私鑰"""
    print("🔑 生成 CSR (憑證請求)...")
    try:
        # 生成私鑰 - 使用 subprocess.run 並設定 timeout 防止卡住
        print("正在生成私鑰...")
        private_key_cmd = [
            "openssl", "genrsa",
            "-out", private_key_path,
            "2048"  # 2048 位 RSA 密鑰
        ]
        subprocess.run(private_key_cmd, check=True, capture_output=True, text=True, timeout=30)
        print(f"✅ 私鑰已生成: {private_key_path}")
        
        # 檢查私鑰是否已生成
        if not os.path.exists(private_key_path) or os.path.getsize(private_key_path) == 0:
            raise Exception(f"私鑰檔案未成功生成: {private_key_path}")
        
        # 生成 CSR - 使用簡單的 subject
        print("正在生成 CSR...")
        
        # 使用簡單的預設值 - 只包含必要的 CN 字段
        subject = f"/CN=Apple Development: {apple_id}"
            
        csr_cmd = [
            "openssl", "req",
            "-new",
            "-key", private_key_path,
            "-out", csr_path,
            "-subj", subject,
            "-nodes",  # 不加密私鑰
            "-batch"   # 使用批處理模式，不需要互動
        ]
        
        subprocess.run(csr_cmd, check=True, capture_output=True, text=True, timeout=30)
        print(f"✅ CSR 已生成: {csr_path}")
        
        # 檢查 CSR 是否已生成
        if not os.path.exists(csr_path) or os.path.getsize(csr_path) == 0:
            raise Exception(f"CSR 檔案未成功生成: {csr_path}")
        
    except subprocess.TimeoutExpired:
        print(f"❌ OpenSSL 命令執行超時")
        # 嘗試清理未完成的檔案
        for path in [private_key_path, csr_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"已刪除未完成的檔案: {path}")
                except:
                    pass
        raise Exception("生成 CSR 時命令執行超時")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 生成 CSR 時發生錯誤: {e}")
        print(f"錯誤輸出: {e.stderr}")
        raise Exception(f"生成 CSR 失敗: {e.stderr}")
        
    except Exception as e:
        print(f"❌ 意外錯誤: {str(e)}")
        raise
    
def submit_csr_to_apple(token, csr_path):
    """把 CSR 提交至 Apple 產生憑證"""
    if not os.path.exists(csr_path):
        raise FileNotFoundError(f"CSR 文件不存在: {csr_path}")
    with open(csr_path, "rb") as f:
        csr_raw_content = f.read()
    csr_text = csr_raw_content.decode('utf-8', errors='ignore')
    clean_csr = csr_text.replace("-----BEGIN CERTIFICATE REQUEST-----", "") \
                        .replace("-----END CERTIFICATE REQUEST-----", "") \
                        .replace("\n", "").strip()
    csr_content = clean_csr
    url = "https://api.appstoreconnect.apple.com/v1/certificates"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "data": {
            "type": "certificates",
            "attributes": {
                "certificateType": "IOS_DISTRIBUTION",
                "csrContent": csr_content
            }
        }
    }
    print("📡 向 Apple 提交 CSR，請求新憑證...")
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        certificate = response.json()["data"]
        cert_content = certificate["attributes"]["certificateContent"]
        cert_id = certificate["id"]
        certs_dir = config.cert_dir_path
        cert_path = os.path.join(certs_dir, f"{cert_id}.cer")
        with open(cert_path, "wb") as f:
            f.write(base64.b64decode(cert_content))
        print(f"✅ 憑證建立成功！\n憑證 ID: {cert_id}\n已儲存於: {cert_path}")
        return cert_id
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 錯誤: {e}")
        print(f"錯誤詳情: {response.text}")
        raise  # 重新拋出異常
    except Exception as e:
        print(f"❌ 意外錯誤: {str(e)}")
        raise

def create_certificate(apple_id):
    """透過 Apple API 創建 iOS Distribution 憑證"""
    print("📜 開始創建憑證流程...")
    account = apple_accounts.get_account_by_apple_id(apple_id)
    key_id = account['key_id']
    certs_dir = config.cert_dir_path
    csr_path = os.path.join(certs_dir, f"{key_id}.certSigningRequest")
    private_key_path = os.path.join(certs_dir, f"{key_id}.pem")
    cert_path = None  
    try:
        # 檢查並移除舊憑證
        removed_cert_id = revoke_oldest_distribution_certificate(apple_id)
        if removed_cert_id:
            remove_keychain_certificate_by_id(removed_cert_id)
            local_file.remove_local_files(apple_id)
        else:
            print(f"✅ 並無需要刪除的憑證")
        # 生成 CSR 和私鑰
        generate_csr(apple_id, csr_path, private_key_path)
        # 提交 CSR 並獲取憑證
        cert_id = submit_csr_to_apple(token=auth.generate_token(apple_id), csr_path=csr_path)
        cert_path = os.path.join(certs_dir, f"{cert_id}.cer")
        # 導入 Keychain
        keychain.import_cert_to_keychain(private_key_path, cert_path)
        print("✅ 憑證創建流程完成")
        return cert_id
    except Exception as e:
        print(f"❌ 憑證創建失敗: {str(e)}")
        raise  # 讓上層調用者處理異常
    finally:
        # 清理臨時檔案
        for path in [csr_path, private_key_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"🗑️ 已刪除臨時檔案: {path}")
                except OSError as e:
                    print(f"❌ 刪除檔案失敗: {path}, 錯誤: {e}")
    





