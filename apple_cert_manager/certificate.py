import subprocess
import os
from . import auth
import re
import hashlib
import base64
import logging
from . import apple_accounts
from . import local_file
from apple_cert_manager.http_client import http_client
from apple_cert_manager.config import config 
from . import keychain
from datetime import datetime
        
logging = logging.getLogger(__name__)
        
def revoke_certificate(apple_id, cert_id):
    """從 App Store Connect 刪除指定憑證。

    Args:
        apple_id (str): Apple 開發者帳號 ID。
        cert_id (str): 憑證 ID。

    Raises:
        ValueError: 如果 token 無效。
        requests.exceptions.RequestException: 如果 API 請求失敗。
    """
    try:
        token = auth.generate_token(apple_id)
        url = f"https://api.appstoreconnect.apple.com/v1/certificates/{cert_id}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        http_client.delete(url, headers=headers)
        logging.info(f"成功刪除遠端憑證 ID: {cert_id}")
    except Exception as e:
        raise Exception(f"刪除憑證失敗: {e}")
        
def revoke_oldest_distribution_certificate(apple_id):
    """如果 `DISTRIBUTION` 類型憑證超過 2 個，則刪除最早過期的。

    Args:
        apple_id (str): Apple 開發者帳號 ID。

    Returns:
        str or None: 成功刪除的憑證 ID，若無需刪除則返回 None。

    Raises:
        Exception: 如果處理或刪除憑證失敗。
    """
    try:
        all_certs = list_certificates(apple_id)
        distribution_certs = filter_distribution_certificates(all_certs)
        if len(distribution_certs) >= 2:
            # ✅ 取出最早過期的憑證
            distribution_certs.sort(key=lambda cert: cert['attributes']["expirationDate"])
            cert_to_remove = distribution_certs[0]
            cert_id = cert_to_remove["id"]
            cert_name = cert_to_remove['attributes']["name"]
            expiration_date = cert_to_remove['attributes']["expirationDate"]
            logging.info(f"⚠️ `DISTRIBUTION` 類型憑證超過 2 個，準備刪除最早過期的憑證:")
            logging.info(f"  - 憑證名稱: {cert_name}")
            logging.info(f"  - 憑證 ID: {cert_id}")
            logging.info(f"  - 到期日: {expiration_date}")
            revoke_certificate(apple_id, cert_id)
            logging.info(f"✅ 成功刪除最早過期的憑證: {cert_name} ({cert_id})")
            if cert_id:
                remove_keychain_certificate_by_id(cert_id)
                local_file.remove_local_files(cert_id)
            else:
                logging.info("並無需要刪除的憑證")
            return cert_id
        else:
            logging.info("✅ `DISTRIBUTION` 憑證數量符合規範，不需要刪除")
    except Exception as e:
        raise Exception(f"刪除憑證失敗: {e}")
    
        
def format_expiration_date(expiration):
    """格式化日期。

    Args:
        expiration (str): ISO 格式的日期字串。

    Returns:
        str: 格式化後的日期，或 "Invalid date" 如果解析失敗。
    """
    try:
        exp_date = datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%S.%f%z")
        return exp_date.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Invalid date"
    
def list_certificates(apple_id):
    """列出 App Store Connect 上的憑證。

    Args:
        apple_id (str): Apple 開發者帳號 ID。

    Returns:
        list: 憑證列表。

    Raises:
        ValueError: 如果 token 無效。
        requests.exceptions.RequestException: 如果 API 請求失敗。
        KeyError: 如果回應格式無效。
    """
    url = "https://api.appstoreconnect.apple.com/v1/certificates"
    try:
        token = auth.generate_token(apple_id)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        response = http_client.get(url, headers=headers)  # 使用 http_client，內含超時和重試
        data = response.json()
        if "data" not in data:
            raise KeyError("list_certificates 無效的 API 回應格式，缺少 'data' 鍵")
        certificates = data["data"]
        logging.info(f"成功獲取 {len(certificates)} 個憑證，Apple ID: {apple_id}")
        for cert in certificates:
            logging.info(f"憑證ID: {cert['id']}, 名稱: {cert['attributes']['name']} 類型: {cert['attributes']['certificateType']} 到期日期: {format_expiration_date(cert['attributes']['expirationDate'])}")
        return certificates
    except Exception as e:
        raise Exception.error(f"獲取憑證列表時發生錯誤: {e}")
    
def filter_distribution_certificates(certificates):
    """過濾 `DISTRIBUTION` 和 `IOS_DISTRIBUTION` 類型的憑證。

    Args:
        certificates (list): 憑證列表。

    Returns:
        list: 過濾後的憑證列表。
    """
    return [
        cert for cert in certificates if cert['attributes']['certificateType'] in ["DISTRIBUTION", "IOS_DISTRIBUTION"]
    ]

def find_private_key(cert_name, keychain_path):
    """搜尋私鑰。

    Args:
        cert_name (str): 憑證名稱。

    Returns:
        str or None: 私鑰的 SHA-1 哈希值，若未找到則返回 None。
    """
    search_command = ["security", "find-identity", "-v", "-p", "codesigning", keychain_path]
    result = subprocess.run(search_command, capture_output=True, text=True)
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            if cert_name in line:
                matches = re.findall(r'([A-F0-9]{40})', line, re.IGNORECASE)
                if matches:
                    return matches[0]
    return None

def get_cert_name_from_file(cert_file_path):
    """從 `.cer` 檔案讀取憑證名稱 (Common Name) 並去除 Team ID。

    Args:
        cert_file_path (str): 憑證檔案路徑。

    Returns:
        str or None: 憑證名稱，若失敗則返回 None。
    """
    if not os.path.exists(cert_file_path):
        logging.warning(f"憑證檔案不存在: {cert_file_path}")
        return None
    get_cert_name_command = ["openssl", "x509", "-noout", "-subject", "-in", cert_file_path]
    result = subprocess.run(get_cert_name_command, capture_output=True, text=True)
    common_name_match = re.search(r"CN\s?=\s?([^,]+)", result.stdout)
    cert_name = common_name_match.group(1).strip() if common_name_match else None
    if cert_name:
        cert_name = re.sub(r"\s*\(.*?\)$", "", cert_name)
    return cert_name

def get_cer_sha1(cert_id):
    """計算 `.cer` 檔案的 SHA-1 哈希值。

    Args:
        cert_id (str): 憑證 ID。

    Returns:
        str or None: SHA-1 哈希值，若失敗則返回 None。
    """
    cert_file_path = os.path.join(config.cert_dir_path, f"{cert_id}.cer")
    if not os.path.exists(cert_file_path):
        logging.warning(f"憑證檔案不存在: {cert_file_path}")
        return None
    sha1 = hashlib.sha1()
    with open(cert_file_path, "rb") as f:
        while chunk := f.read(4096):
            sha1.update(chunk)
    return sha1.hexdigest().upper()

def remove_keychain_certificate(cert):
    """從 macOS Keychain 刪除指定的憑證與私鑰。

    Args:
        cert (dict): 憑證資料，包含 'attributes' 鍵。

    """
    if not isinstance(cert, dict) or 'attributes' not in cert or 'name' not in cert['attributes']:
        raise ValueError("無效的憑證資料，缺少 'attributes' 或 'name'")
    
    cert_name = cert['attributes']['name']
    keychain_path = os.path.expanduser(config.keychain_path)
    keychain.unlock_keychain()
    key_hash = find_private_key(cert_name, keychain_path)
    if key_hash:
        delete_identity_command = ["security", "delete-identity", "-Z", key_hash, keychain_path]
        subprocess.run(delete_identity_command, check=True, capture_output=True, text=True)
        logging.info(f"成功刪除憑證 '{cert_name}' 的私鑰和相關聯身份")
    else:
        logging.error(f"未找到與憑證名稱 '{cert_name}' 相關的私鑰")
    

def remove_keychain_certificate_by_id(cert_id):
    """透過 `cert_id` 刪除 macOS Keychain 中的憑證與私鑰。

    Args:
        cert_id (str): 憑證 ID。
    """
    keychain_path = os.path.expanduser(config.keychain_path)
    cert_file_path = get_cert_path(cert_id)
    keychain.unlock_keychain()
    cert_name = get_cert_name_from_file(cert_file_path)
    if not cert_name:
        logging.error(f"無法從 `.cer` 檔案 '{cert_file_path}' 讀取憑證名稱")
        return
    
    key_hash = find_private_key(cert_name, keychain_path)
    if not key_hash:
        logging.error(f"未找到與憑證名稱 '{cert_name}' 相關的私鑰")
    
    delete_identity_command = ["security", "delete-identity", "-Z", key_hash, keychain_path]
    subprocess.run(delete_identity_command, check=True, capture_output=True, text=True)
    logging.info(f"成功刪除憑證 ID '{cert_id}' 的私鑰和相關聯身份")
    
def get_cert_path(cert_id):
    """生成憑證檔案路徑。

    Args:
        cert_id (str): 憑證 ID。

    Returns:
        str: 檔案路徑。
    """
    return os.path.join(config.cert_dir_path, f"{cert_id}.cer")

def generate_csr(apple_id, csr_path, private_key_path):
    """使用 OpenSSL 生成 CSR (憑證請求) 和私鑰。

    Args:
        apple_id (str): Apple 開發者帳號 ID。
        csr_path (str): CSR 檔案儲存路徑。
        private_key_path (str): 私鑰儲存路徑。

    Raises:
        subprocess.CalledProcessError: 如果 OpenSSL 命令失敗。
        subprocess.TimeoutExpired: 如果命令超時。
        OSError: 如果檔案操作失敗。
    """
    logging.info("正在生成私鑰...")
    private_key_cmd = ["openssl", "genrsa", "-out", private_key_path, "2048"]
    subprocess.run(private_key_cmd, check=True, capture_output=True, text=True, timeout=30)
    if not os.path.exists(private_key_path) or os.path.getsize(private_key_path) == 0:
        raise OSError(f"私鑰檔案未成功生成: {private_key_path}")
    logging.info(f"私鑰已生成: {private_key_path}")
    logging.info("正在生成 CSR...")
    subject = f"/CN=Apple Development: {apple_id}"
    csr_cmd = [
        "openssl", "req", "-new", "-key", private_key_path, "-out", csr_path,
        "-subj", subject, "-nodes", "-batch"
    ]
    subprocess.run(csr_cmd, check=True, capture_output=True, text=True, timeout=30)
    if not os.path.exists(csr_path) or os.path.getsize(csr_path) == 0:
        raise OSError(f"CSR 檔案未成功生成: {csr_path}")
    logging.info(f"CSR 已生成: {csr_path}")
    
def submit_csr_to_apple(token, csr_path):
    """把 CSR 提交至 Apple 產生憑證。

    Args:
        token (str): JWT token。
        csr_path (str): CSR 檔案路徑。

    Returns:
        str: 新憑證的 ID。

    Raises:
        FileNotFoundError: 如果 CSR 檔案不存在。
        requests.exceptions.RequestException: 如果 API 請求失敗。
    """
    if not os.path.exists(csr_path):
        raise FileNotFoundError(f"CSR 檔案不存在: {csr_path}")
    
    logging.info("向 Apple 提交 CSR，請求新憑證...")
    with open(csr_path, "rb") as f:
        csr_raw_content = f.read()
    csr_text = csr_raw_content.decode('utf-8', errors='ignore')
    clean_csr = csr_text.replace("-----BEGIN CERTIFICATE REQUEST-----", "") \
                        .replace("-----END CERTIFICATE REQUEST-----", "") \
                        .replace("\n", "").strip()
    
    url = "https://api.appstoreconnect.apple.com/v1/certificates"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "data": {
            "type": "certificates",
            "attributes": {
                "certificateType": "IOS_DISTRIBUTION",
                "csrContent": clean_csr
            }
        }
    }
    response = http_client.post(url, headers=headers, json=payload)
    data = response.json()
    if "data" not in data:
            raise KeyError("submit_csr_to_apple 無效的 API 回應格式，缺少 'data' 鍵")
    certificate = data["data"]
    cert_content = certificate["attributes"]["certificateContent"]
    cert_id = certificate["id"]
    cert_path = get_cert_path(cert_id)
    with open(cert_path, "wb") as f:
        f.write(base64.b64decode(cert_content))
    logging.info(f"憑證建立成功！憑證 ID: {cert_id}，已儲存於: {cert_path}")
    return cert_id
    
def create_certificate(apple_id):
    """透過 Apple API 創建 iOS Distribution 憑證。

    Args:
        apple_id (str): Apple 開發者帳號 ID。

    Returns:
        str: 新憑證的 ID。

    Raises:
        Exception: 如果創建流程失敗。
    """
    logging.info("開始創建憑證流程...")
    account = apple_accounts.get_account_by_apple_id(apple_id)
    key_id = account['key_id']
    certs_dir = config.cert_dir_path
    csr_path = os.path.join(certs_dir, f"{key_id}.certSigningRequest")
    private_key_path = os.path.join(certs_dir, f"{key_id}.pem")
    try:
        revoke_oldest_distribution_certificate(apple_id)
        generate_csr(apple_id, csr_path, private_key_path)
        token = auth.generate_token(apple_id)
        cert_id = submit_csr_to_apple(token, csr_path)
        cert_path = get_cert_path(cert_id)
        keychain.import_cert_to_keychain(private_key_path, cert_path)
        logging.info("憑證創建流程完成")
        return cert_id
    except Exception as e:
        raise Exception(f"憑證創建失敗: {apple_id} 錯誤:{e}")
    finally:
        for path in [csr_path, private_key_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as e:
                    logging.error(f"刪除檔案失敗: {path}, 錯誤: {e}")
    





