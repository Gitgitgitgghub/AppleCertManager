import base64
import logging
import requests
from datetime import datetime
from . import apple_accounts
from apple_cert_manager.http_client import http_client
from apple_cert_manager.config import config
from . import auth

logging = logging.getLogger(__name__)

# 集中 API URL
API_BASE_URL = "https://api.appstoreconnect.apple.com/v1"

def get_api_token(apple_id):
    """生成並驗證 API token"""
    token = auth.generate_token(apple_id)
    if not token:
        raise ValueError(f"無法生成 token，Apple ID: {apple_id}")
    return token

def get_headers(token):
    """生成標準 HTTP headers"""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def get_profile_path(filename):
    """生成 Provisioning Profile 檔案路徑"""
    return f"{config.profile_dir_path}/{filename}"

def validate_api_response(data, func_name):
    """驗證 API 回應格式"""
    if "data" not in data:
        raise KeyError(f"{func_name} 無效的 API 回應格式，缺少 'data' 鍵")
    return data["data"]

def get_all_devices(token, return_ids_only=False):
    """獲取 Apple Developer 帳號下的所有裝置資料或 ID"""
    logging.info("正在獲取所有裝置列表...")
    url = f"{API_BASE_URL}/devices"
    headers = get_headers(token)
    response = http_client.get(url, headers=headers)
    devices = validate_api_response(response.json(), "get_all_devices")
    
    if not devices:
        raise ValueError("無可用裝置，請先在 Apple Developer 帳號中新增至少一台裝置")
    
    logging.info(f"已找到 {len(devices)} 台裝置")
    if return_ids_only:
        device_ids = [d["id"] for d in devices]
        return device_ids
    return devices

def find_existing_profile(token, file_name):
    """查找現有的 Provisioning Profile"""
    logging.info(f"正在查找描述檔：{file_name}...")
    url = f"{API_BASE_URL}/profiles?filter[name]={file_name}"
    headers = get_headers(token)
    response = http_client.get(url, headers=headers)
    profiles = validate_api_response(response.json(), "find_existing_profile")
    
    if profiles:
        profile_id = profiles[0]["id"]
        logging.info(f"找到現有描述檔：{file_name}（ID: {profile_id}）")
        return profile_id
    logging.info(f"未找到 {file_name}，將建立新描述檔")
    return None

def delete_existing_profile(token, profile_id):
    """刪除舊的 Provisioning Profile"""
    if profile_id:
        logging.info(f"正在刪除描述檔（ID: {profile_id}）...")
        url = f"{API_BASE_URL}/profiles/{profile_id}"
        headers = get_headers(token)
        http_client.delete(url, headers=headers)
        logging.info(f"成功刪除描述檔（ID: {profile_id}）")

def create_new_profile(token, cert_id, file_name, bundle_id, device_ids):
    """創建新的 Ad Hoc Provisioning Profile"""
    logging.info("正在建立新的 Ad Hoc 描述檔...")
    logging.info(cert_id)
    logging.info(file_name)
    logging.info(bundle_id)
    url = f"{API_BASE_URL}/profiles"
    payload = {
        "data": {
            "type": "profiles",
            "attributes": {
                "name": file_name,
                "profileType": "IOS_APP_ADHOC"
            },
            "relationships": {
                "bundleId": {"data": {"type": "bundleIds", "id": bundle_id}},
                "certificates": {"data": [{"type": "certificates", "id": cert_id}]},
                "devices": {"data": [{"type": "devices", "id": did} for did in device_ids]}
            }
        }
    }
    headers = get_headers(token)
    response = http_client.post(url, headers=headers, json=payload)
    new_profile = validate_api_response(response.json(), "create_new_profile")
    profile_id = new_profile["id"]
    logging.info(f"成功建立描述檔：{file_name}（ID: {profile_id}）")
    return new_profile["attributes"]["profileContent"]

def download_profile(output_path, profile_content):
    """儲存 Base64 編碼的 Provisioning Profile 到本地檔案"""
    if not profile_content:
        raise ValueError("沒有有效的 Provisioning Profile 內容")
    if not output_path:
        raise ValueError("輸出路徑無效")
    
    logging.info(f"正在儲存描述檔至：{output_path}...")
    profile_data = base64.b64decode(profile_content)
    with open(output_path, "wb") as f:
        f.write(profile_data)
    logging.info(f"成功儲存描述檔至：{output_path}")

def list_all_bundle_ids(token):
    """列出 Apple Developer 帳號內所有的 Bundle ID"""
    logging.info("正在獲取所有 Bundle ID...")
    url = f"{API_BASE_URL}/bundleIds"
    headers = get_headers(token)
    response = http_client.get(url, headers=headers)
    bundles = validate_api_response(response.json(), "list_all_bundle_ids")
    
    if not bundles:
        raise ValueError("未找到任何 Bundle ID，請確認帳號是否已註冊 App ID")
    
    logging.info("找到以下 Bundle ID：")
    for item in bundles:
        logging.info(f"- {item['attributes']['identifier']} (ID: {item['id']})")
    return bundles

def create_bundle_id(token, identifier, name=None, platform="IOS"):
    """新增一個 Bundle ID"""
    logging.info(f"正在新增 Bundle ID: {identifier}...")
    # 如果未提供名稱，預設使用 identifier 作為名稱
    if not name:
        name = identifier.replace(".", " ")
    
    # 構建請求 payload
    payload = {
        "data": {
            "type": "bundleIds",
            "attributes": {
                "identifier": identifier,  # Bundle ID 的唯一識別符，例如 com.example.myapp
                "name": name,              # Bundle ID 的顯示名稱
                "platform": platform       # 平台，可選 IOS 或 MAC_OS
            }
        }
    }
    url = f"{API_BASE_URL}/bundleIds"
    headers = get_headers(token)
    
    try:
        response = http_client.post(url, headers=headers, json=payload)
        bundle_data = validate_api_response(response.json(), "create_bundle_id")
        bundle_id = bundle_data["id"]
        logging.info(f"成功新增 Bundle ID: {identifier}（ID: {bundle_id}）")
        return bundle_id
    except requests.exceptions.HTTPError as e:
        error_msg = f"新增 Bundle ID {identifier} 失敗: {e.response.status_code} - {e.response.text}"
        logging.error(error_msg)
        raise ValueError(error_msg) from e

def get_provisioning_profile(apple_id, progress=None, task_id=None):
    """主函數：獲取或重新創建最新的 Provisioning Profile 並下載"""
    logging.info("啟動 Provisioning Profile 處理流程...")
    steps = 6  # 總步驟數
    step_increment = 100 / steps if progress and task_id else 0
    
    account = apple_accounts.get_account_by_apple_id(apple_id)
    if not account:
        raise ValueError(f"找不到 Apple ID: {apple_id}")
    cert_id = account['cert_id']
    if not cert_id:
        raise ValueError(f"Apple ID: {apple_id} 沒有對應的 cert_id")
    # 檢查.env bundle id是否有正確配置
    env_bundle_id = config.bundle_id
    if not env_bundle_id:
        raise ValueError(f"未找到 BUNDLE_ID 請檢查 .env BUNDLE_ID是否有配置")
    if progress and task_id:
        progress.update(task_id, advance=step_increment)  # 步驟 1: 初始化
    
    token = get_api_token(apple_id)
    filename = f"adhoc_{cert_id}.mobileprovision"
    output_path = get_profile_path(filename)
    
    if progress and task_id:
        progress.update(task_id, advance=step_increment)  # 步驟 2: 獲取裝置
    device_ids = get_all_devices(token, return_ids_only=True)
    
    if progress and task_id:
        progress.update(task_id, advance=step_increment)  # 步驟 3: 獲取 Bundle ID

    all_bundles = list_all_bundle_ids(token)
    # 這裡開始 bundle_id 會是網站上的bundle_id的索引 不會是com.example....這類的
    bundle_id = None
    for bundle in all_bundles:
        if bundle["attributes"]["identifier"] == env_bundle_id:
            bundle_id = bundle["id"]
            break
    if not bundle_id:
        bundle_id = create_bundle_id(token, env_bundle_id)
    
    if progress and task_id:
        progress.update(task_id, advance=step_increment)  # 步驟 4: 處理現有描述檔
    profile_id = find_existing_profile(token, filename)
    if profile_id:
        delete_existing_profile(token, profile_id)
    
    if progress and task_id:
        progress.update(task_id, advance=step_increment)  # 步驟 5: 創建新描述檔
    profile_content = create_new_profile(token, cert_id, filename, bundle_id, device_ids)
    
    if progress and task_id:
        progress.update(task_id, advance=step_increment)  # 步驟 6: 下載
    download_profile(output_path, profile_content)
    
    logging.info("Provisioning Profile 處理流程完成")
    if progress and task_id:
        progress.update(task_id, completed=100)

def register_device(apple_id, device_name, device_udid):
    """在 Apple Developer 帳號中註冊新裝置"""
    logging.info(f"正在註冊新裝置：{device_name} (UDID: {device_udid})...")
    token = get_api_token(apple_id)
    url = f"{API_BASE_URL}/devices"
    headers = get_headers(token)
    payload = {
        "data": {
            "type": "devices",
            "attributes": {
                "name": device_name,
                "udid": device_udid,
                "platform": "IOS"
            }
        }
    }
    try:
        response = http_client.post(url, headers=headers, json=payload)
        device_info = response.json()["data"]
        logging.info(f"成功註冊裝置：{device_info['attributes']['name']} (ID: {device_info['id']})")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409 and "already exists on this team" in e.response.text:
            logging.info(f"裝置已存在，繼續執行 get_provisioning_profile")
            get_provisioning_profile(apple_id)
        else:
            raise Exception(f"註冊裝置失敗: {e}")
        
#-------------下方式測試用的目前沒使用-----------------------#

# 未使用的測試函數（保持不變，但改進格式）
def get_device_id_by_udid(token, udid):
    """透過 UDID 查找 Apple API 內部的 Device ID"""
    devices = get_all_devices(token)
    if devices:
        for device in devices:
            if device["attributes"]["udid"] == udid:
                return device["id"]
    raise ValueError(f"找不到 UDID: {udid} 對應的 Device ID，請確認裝置已註冊")
        
def disable_device(token, udid):
    """停用 Apple Developer 帳號中的裝置"""
    logging.info(f"嘗試透過 UDID 查找 Device ID...")
    try:
        device_id = get_device_id_by_udid(token, udid)
        logging.info(f"正在停用裝置 ID: {device_id}（UDID: {udid}）...")
        url = f"{API_BASE_URL}/devices/{device_id}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "data": {
                "id": device_id,
                "type": "devices",
                "attributes": {
                    "status": "DISABLED"
                }
            }
        }
        http_client.patch(url, headers=headers, json=payload)
        logging.info(f"成功停用裝置（ID: {device_id}，UDID: {udid}）")
    except Exception as e:
        raise Exception(f"disable_device 錯誤: {e}")

def get_all_profiles(token):
    """獲取 Apple Developer 帳號下所有 Provisioning Profile"""
    logging.info("正在獲取所有描述檔列表...")
    url = f"{API_BASE_URL}/profiles"
    headers = get_headers(token)
    response = http_client.get(url, headers=headers)
    profiles = validate_api_response(response.json(), "get_all_profiles")
    
    if not profiles:
        logging.info("未找到任何描述檔")
        return []
    logging.info(f"找到 {len(profiles)} 個描述檔")
    return profiles

def is_profile_valid(profile):
    """檢查描述檔是否有效（未過期）"""
    expiration_date_str = profile["attributes"].get("expirationDate")
    profile_state = profile["attributes"].get("profileState")
    
    # 檢查 profileState 是否為 INVALID
    if profile_state == "INVALID":
        logging.debug(f"描述檔 {profile['attributes']['name']} 狀態為 INVALID，視為無效")
        return False
    
    if not expiration_date_str:
        logging.warning(f"描述檔 {profile['attributes']['name']} 缺少 expirationDate，視為無效")
        return False
    
    exp_date = datetime.strptime(expiration_date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    
    is_valid = exp_date > datetime.now(exp_date.tzinfo)
    logging.debug(f"檢查描述檔 {profile['attributes']['name']}：過期日期 {exp_date}, 是否有效: {is_valid}")
    return is_valid

def delete_profile(token, profile_id):
    """刪除指定的 Provisioning Profile"""
    logging.info(f"正在刪除描述檔（ID: {profile_id}）...")
    url = f"{API_BASE_URL}/profiles/{profile_id}"
    headers = get_headers(token)
    http_client.delete(url, headers=headers)
    logging.info(f"成功刪除描述檔（ID: {profile_id}）")

def cleanup_invalid_profiles(apple_id, progress=None, task_id=None):
    """取得所有描述檔並刪除無效的描述檔"""
    logging.info("開始清理無效的 Provisioning Profile...")
    token = get_api_token(apple_id)
    
    # 步驟 1: 獲取所有描述檔
    profiles = get_all_profiles(token)
    if not profiles:
        logging.info("無描述檔需要清理")
        return
    
    total_profiles = len(profiles)
    steps = 2  # 獲取描述檔 + 處理無效描述檔
    step_increment = 100 / steps if progress and task_id else 0
    
    if progress and task_id:
        progress.update(task_id, advance=step_increment)  # 步驟 1 完成
    
    # 步驟 2: 檢查並刪除無效描述檔
    invalid_profiles = [p for p in profiles if not is_profile_valid(p)]
    if not invalid_profiles:
        logging.info("未找到無效的描述檔")
        return
    
    logging.info(f"找到 {len(invalid_profiles)} 個無效描述檔，將進行清理")
    if progress and task_id:
        cleanup_task = progress.add_task("[yellow]清理無效描述檔", total=len(invalid_profiles))
    
    for profile in invalid_profiles:
        profile_id = profile["id"]
        profile_name = profile["attributes"]["name"]
        try:
            delete_profile(token, profile_id)
            logging.info(f"已清理無效描述檔：{profile_name}（ID: {profile_id}）")
            if progress and cleanup_task:
                progress.update(cleanup_task, advance=1)
        except Exception as e:
            logging.error(f"清理描述檔 {profile_name}（ID: {profile_id}）失敗: {e}")
    
    if progress and task_id:
        progress.update(task_id, advance=step_increment)  # 步驟 2 完成
    logging.info("無效描述檔清理完成")

