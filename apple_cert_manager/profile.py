import subprocess
import requests
import base64
from . import apple_accounts
from apple_cert_manager.config import config 
from . import auth

def get_all_devices(token):
    """獲取 Apple Developer 帳號下所有裝置 ID，若無裝置則回報錯誤"""
    print("🔍 正在取得 Apple 開發者帳號下的裝置列表...")
    devices_url = "https://api.appstoreconnect.apple.com/v1/devices"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.get(devices_url, headers=headers)

    if response.status_code == 200:
        devices = response.json()["data"]
        if not devices:  
            print("❌ 無可用裝置，請先在 Apple Developer 帳號中新增至少一台裝置！")
            return None 
        device_ids = [d["id"] for d in devices]
        print(f"✅ 已找到 {len(device_ids)} 台裝置，將套用到描述檔。")
        return device_ids
    else:
        print(f"❌ 無法獲取裝置列表，錯誤資訊：{response.text}")
        return None

def find_existing_profile(token, file_name):
    """查找現有的 Provisioning Profile"""
    print(f"🔍 正在查找是否已存在名稱為 {file_name} 的描述檔...")
    profiles_url = f"https://api.appstoreconnect.apple.com/v1/profiles?filter[name]={file_name}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.get(profiles_url, headers=headers)
    profiles = response.json()

    if profiles["data"]:
        profile_id = profiles["data"][0]["id"]
        print(f"✅ 已找到現有的描述檔：{file_name}（ID: {profile_id}）")
        return profile_id
    print(f"⚠️ 未找到 {file_name}，將建立新的描述檔。")
    return None

def delete_existing_profile(token, profile_id):
    """刪除舊的 Provisioning Profile"""
    if profile_id:
        print(f"🗑️ 刪除舊的描述檔：（ID: {profile_id}）...")
        delete_url = f"https://api.appstoreconnect.apple.com/v1/profiles/{profile_id}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        requests.delete(delete_url, headers=headers)
        print(f"✅ 成功刪除 {profile_id}")

def create_new_profile(token, cert_id, file_name, bundle_id_api, device_ids):
    """創建新的 Ad Hoc Provisioning Profile"""
    create_url = "https://api.appstoreconnect.apple.com/v1/profiles"
    payload = {
        "data": {
            "type": "profiles",
            "attributes": {
                "name": file_name,
                "profileType": "IOS_APP_ADHOC"
            },
            "relationships": {
                "bundleId": {"data": {"type": "bundleIds", "id": bundle_id_api}},
                "certificates": {"data": [{"type": "certificates", "id": cert_id}]},
                "devices": {"data": [{"type": "devices", "id": did} for did in device_ids]}
            }
        }
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("🛠️ 正在建立新的 Ad Hoc 描述檔...")
    response = requests.post(create_url, headers=headers, json=payload)
    if response.status_code == 201:
        new_profile = response.json()
        profile_id = new_profile["data"]["id"]
        print(f"✅ 已成功建立新的描述檔：{file_name}（ID: {profile_id}）")
        return new_profile["data"]["attributes"]["profileContent"]
    else:
        print(f"❌ 描述檔建立失敗，錯誤資訊：{response.text}")
        return None

def download_profile(output_path, profile_content):
    """儲存 Base64 編碼的 Provisioning Profile 到本地檔案"""
    if not profile_content:
        print("❌ 錯誤：沒有有效的 Provisioning Profile 內容")
        return
    
    try:
        profile_data = base64.b64decode(profile_content)  # **解碼 Base64**
        with open(output_path, "wb") as f:
            f.write(profile_data)
        print(f"✅ 描述檔已成功儲存至：{output_path}")
    except Exception as e:
        print(f"❌ 無法儲存描述檔，錯誤：{e}")
            
def list_all_bundle_ids(token):
    """列出 Apple Developer 帳號內所有的 Bundle ID"""
    print("🔍 正在獲取所有 Bundle ID...")
    url = "https://api.appstoreconnect.apple.com/v1/bundleIds"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()["data"]
        if not data:
            print("❌ 沒有找到任何 Bundle ID，請確認你的帳號是否已經註冊 App ID。")
            return None
        
        print("✅ 找到以下 Bundle ID：")
        for item in data:
            print(f"- {item['attributes']['identifier']} (ID: {item['id']})")
        return data
    else:
        print(f"❌ 無法獲取 Bundle ID，錯誤資訊：{response.text}")
        return None

def get_provisioning_profile(apple_id):
    """主函數：獲取或重新創建最新的 Provisioning Profile 並下載"""
    account = apple_accounts.get_account_by_apple_id(apple_id)
    if not account:
        print(f"❌ 找不到 Apple ID: {apple_id}，無法取得憑證")
        return False
    cert_id = account["cert_id"]
    token = auth.generate_token(apple_id)
    filename = f"adhoc_{cert_id}.mobileprovision"
    output_path = f"{config.profile_dir_path}/{filename}"
    if not cert_id:
        print(f"❌ Apple ID: {apple_id} 沒有對應的 cert_id，無法建立 Provisioning Profile")
        return False
    print("🚀 啟動 Provisioning Profile 自動處理流程...")
    # 取得所有註冊的裝置如果是空的會無法建立描述檔
    device_ids = get_all_devices(token)
    if not device_ids:
        print("⚠️ 無法建立 Ad Hoc 描述檔，請先新增至少一台裝置！")
        return False
    # 每個bundle id會有自己的 identifier
    bundle_id_api = None
    all_bundles = list_all_bundle_ids(token)
    if all_bundles:
        for bundle in all_bundles:
            if bundle["attributes"]["identifier"] == config.bundle_id:
                bundle_id_api = bundle["id"]
                break
    if not bundle_id_api:
        print(f"❌ 無法找到 App ID：{config.bundle_id}，請確認已在 Apple Developer 註冊。")
        return False
    # 找到對應描述檔的id並且刪除，不然沒辦法套用新的裝置
    profile_id = find_existing_profile(token, filename)
    if profile_id:
        delete_existing_profile(token, profile_id)
    # 創建新的描述檔案並且套用所有裝置
    profile_content = create_new_profile(token, cert_id, filename, bundle_id_api, device_ids)
    # 描述檔創建成功會回傳一個base64 存起來
    if profile_content:
        download_profile(output_path ,profile_content)
        return True
    
    return False

def register_device(apple_id, device_name, device_udid):
    """在 Apple Developer 帳號中註冊新裝置，若裝置已存在則忽略錯誤，否則中斷"""
    print(f"📲 正在註冊新裝置：{device_name} (UDID: {device_udid})...")
    token = auth.generate_token(apple_id)
    register_url = "https://api.appstoreconnect.apple.com/v1/devices"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "data": {
            "type": "devices",
            "attributes": {
                "name": device_name,
                "udid": device_udid,
                "platform": "IOS"  # iOS 設備，如果是 Mac，改為 "MAC_OS"
            }
        }
    }
    response = requests.post(register_url, headers=headers, json=payload)
    # **成功後繼續執行**
    if response.status_code == 201:
        device_info = response.json()["data"]
        print(f"✅ 成功註冊裝置：{device_info['attributes']['name']} (ID: {device_info['id']})")
        get_provisioning_profile(apple_id)  
    # **檢查是否是 "裝置已存在" 的錯誤，裝置已存在時繼續執行**
    elif response.status_code == 409:
        error_detail = response.json().get("errors", [{}])[0].get("detail", "")
        if "already exists on this team" in error_detail:
            print(f"⚠️ 裝置已存在，繼續執行 `get_provisioning_profile({apple_id})`")
            get_provisioning_profile(apple_id)
            return True
        else:
            print(f"❌ 註冊裝置失敗，錯誤資訊：{response.text}")
            return False 
    else:
        print(f"❌ 註冊裝置失敗，錯誤資訊：{response.text}")
        return False
        
#-------------下方式測試用的目前沒使用-----------------------#

def get_device_id_by_udid(token, udid):
    """透過 UDID 查找 Apple API 內部的 Device ID"""
    devices = get_all_devices_json(token)
    if devices:
        for device in devices:
            if device["attributes"]["udid"] == udid:
                return device["id"]
    print(f"❌ 找不到 UDID: {udid} 對應的 Device ID，請確認裝置已註冊。")
    return None

def get_all_devices_json(token):
    """獲取 Apple Developer 帳號內所有裝置"""
    print("📱 正在獲取所有裝置列表...")
    url = "https://api.appstoreconnect.apple.com/v1/devices"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        devices = response.json()
        if not devices.get("data"):  
            print("❌ 沒有找到任何裝置。")
            return None

        print("✅ 找到以下裝置：")
        for device in devices["data"]:
            print(f"- {device['attributes']['name']} (ID: {device['id']}, UDID: {device['attributes']['udid']}, Status: {device['attributes']['status']})")
        
        return devices["data"] 
    else:
        print(f"❌ 無法獲取裝置列表，錯誤資訊：{response.text}")
        return None
        
def disable_device(token, udid):
    """停用 Apple Developer 帳號中的裝置"""
    print(f"🔍 嘗試透過 UDID 查找 Device ID...")
    device_id = get_device_id_by_udid(token, udid)
    if not device_id:
        print(f"❌ 無法找到 UDID: {udid}，該裝置可能未註冊。")
        return False

    print(f"🔻 正在停用裝置 ID: {device_id}（UDID: {udid}）...")
    disable_url = f"https://api.appstoreconnect.apple.com/v1/devices/{device_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "data": {
            "id": device_id,
            "type": "devices",
            "attributes": {
                "status": "DISABLED"  # 停用裝置
            }
        }
    }
    response = requests.patch(disable_url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"✅ 成功停用裝置（ID: {device_id}，UDID: {udid}）")
        return True
    else:
        print(f"❌ 無法停用裝置，錯誤資訊：{response.text}")
        return False


