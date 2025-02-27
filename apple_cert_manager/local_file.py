import os
from apple_cert_manager.config import config 

def remove_local_files(cert_id):
    """ 刪除與 `cert_id` 相關的 `.cer` 和 `.mobileprovision` 檔案 """
    if not cert_id:
        print("⚠️ `cert_id` 為空，無法刪除相關檔案")
        return False

    # ✅ 設定檔案路徑
    cert_dir_path = os.path.expanduser(config.cert_dir_path)  # `.cer` 檔案路徑
    profile_dir_path = os.path.expanduser(config.profile_dir_path)  # `.mobileprovision` 檔案路徑
    p12_file = os.path.join(cert_dir_path, f"{cert_id}.p12")
    cer_file = os.path.join(cert_dir_path, f"{cert_id}.cer")
    csr_file = os.path.join(cert_dir_path, f"{cert_id}.certSigningRequest")
    mobile_provision_file = os.path.join(profile_dir_path, f"adhoc_{cert_id}.mobileprovision")
    
    # ✅ 刪除 `.p12` 文件
    if os.path.exists(p12_file):
        os.remove(p12_file)
        print(f"✅ 成功刪除 `.p12` 文件: {p12_file}")
    else:
        print(f"⚠️ `.p12` 文件不存在: {p12_file}")

    # ✅ 刪除 `.cer` 文件
    if os.path.exists(cer_file):
        os.remove(cer_file)
        print(f"✅ 成功刪除 `.cer` 文件: {cer_file}")
    else:
        print(f"⚠️ `.cer` 文件不存在: {cer_file}")

    # ✅ 刪除 `.certSigningRequest` 文件
    if os.path.exists(csr_file):
        os.remove(csr_file)
        print(f"✅ 成功刪除 `.certSigningRequest` 文件: {csr_file}")
    else:
        print(f"⚠️ `.certSigningRequest` 文件不存在: {csr_file}")

    # ✅ 刪除 `.mobileprovision` 文件
    if os.path.exists(mobile_provision_file):
        os.remove(mobile_provision_file)
        print(f"✅ 成功刪除 `.mobileprovision` 文件: {mobile_provision_file}")
    else:
        print(f"⚠️ `.mobileprovision` 文件不存在: {mobile_provision_file}")

    return True

def remove_api_key_json(key_id):
    api_key_json_dir_path = os.path.expanduser(config.api_key_json_dir_path)
    api_key_json_file = os.path.join(api_key_json_dir_path, f"{key_id}.json")
    # ✅ 刪除 `api_key_json` 文件
    if os.path.exists(api_key_json_file):
        os.remove(api_key_json_file)
        print(f"✅ 成功刪除 `api_key_json` 文件: {api_key_json_file}")
    else:
        print(f"⚠️ `api_key_json` 文件不存在: {api_key_json_file}")
