import subprocess
from . import apple_accounts
from apple_cert_manager.config import config 
from . import auth

def get_provisioning_profile(apple_id):
    """ 執行 Fastlane get_provisioning_profile """
    account = apple_accounts.get_account_by_apple_id(apple_id)
    if not account:
        print(f"❌ 找不到 Apple ID: {apple_id}，無法取得憑證")
        return False
    issuer_id = account["issuer_id"]
    api_key_id = account["key_id"]
    cert_id = account["cert_id"]
    if not cert_id:
        print(f"❌ Apple ID: {apple_id} 沒有對應的 cert_id，無法建立 Provisioning Profile")
        return False
    api_key_json_path = auth.generate_fastlane_api_key_json(apple_id)
    
    if not api_key_json_path:
        print("❌ 產生 API Key JSON 失敗，無法繼續建立憑證")

    # **🚀 設定 Provisioning Profile 名稱 & 檔案名稱**
    provisioning_name = f"adhoc_{cert_id}"  # ✅ `adhoc_<cert_id>`
    filename = f"adhoc_{cert_id}.mobileprovision"  # ✅ `adhoc_<cert_id>.mobileprovision`
    
    app_identifier = config.bundle_id
    output_path = config.profile_dir_path

    try:
        # 🚀 準備 Fastlane 指令
        command = [
            "fastlane", "run", "get_provisioning_profile",
            "adhoc:true",
            f"api_key_path:{api_key_json_path}",
            f"app_identifier:{app_identifier}",
            f"provisioning_name:{provisioning_name}",
            f"cert_id:{cert_id}",
            "force:true",
            f"filename:{filename}",
            f"output_path:{output_path}"
        ]

        # ✅ 執行 Fastlane 指令
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        print("✅ profile 下載成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Fastlane 執行失敗，錯誤訊息：\n{e.stderr}")
        return False

def register_device(apple_id, device_name, udid):
    """ 🚀 註冊新設備，並同步更新 Provisioning Profile """

    # 1️⃣ 🔍 取得 Fastlane API Key JSON
    api_key_json_path = auth.generate_fastlane_api_key_json(apple_id)
    if not api_key_json_path:
        print("❌ 無法取得 API Key JSON，設備註冊失敗")
        return False

    # 2️⃣ 🚀 註冊新設備
    print(f"🔍 註冊設備: {device_name} (UDID: {udid})")
    register_command = [
        "fastlane", "run", "register_device",
        f"api_key_path:{api_key_json_path}",
        f"name:{device_name}",
        f"udid:{udid}"
    ]

    result = subprocess.run(register_command, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ 註冊設備成功: {device_name} (UDID: {udid})")

        # 3️⃣ 🚀 設備註冊成功後，立即更新 Provisioning Profile
        print("🔍 開始更新 `.mobileprovision`...")
        if get_provisioning_profile(apple_id):
            print(f"✅ `.mobileprovision` 更新成功！")
            return True
        else:
            print(f"❌ `.mobileprovision` 更新失敗")
            return False
    else:
        print(f"❌ 註冊設備失敗: {result.stderr}")
        return False

