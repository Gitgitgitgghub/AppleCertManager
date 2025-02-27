import subprocess
import os
import shutil
import plistlib
import concurrent.futures
from apple_cert_manager.config import config 
from . import apple_accounts
from . import keychain
from . import certificate

def run_subprocess(command, description, check=True, **kwargs):
    """通用的子程序運行工具"""
    try:
        #log(f"執行命令: {' '.join(command)}")
        result = subprocess.run(command, check=check, text=True, **kwargs)
        return result
    except subprocess.CalledProcessError as e:
        print(f"{description} 失敗: {e.stderr if e.stderr else str(e)}")
        raise

def extract_ipa(apple_id):
    """ 🚀 根據 `apple_id` 建立專屬目錄，複製 IPA，並解壓 """
    ipa_source_path = config.ipa_path  # 原始 IPA 位置
    ipa_base_dir = os.path.dirname(ipa_source_path)
    # 1️⃣ 🔍 取得 `apple_id` 的前半部分作為目錄名稱
    apple_id_prefix = apple_id.split("@")[0]
    # 2️⃣ 🚀 創建 `ipa/{apple_id_prefix}/` 目錄
    apple_ipa_dir = os.path.join(ipa_base_dir, apple_id_prefix)
    os.makedirs(apple_ipa_dir, exist_ok=True)
    # 3️⃣ 🚀 複製 IPA 到新目錄
    ipa_dest_path = os.path.join(apple_ipa_dir, os.path.basename(ipa_source_path))
    shutil.copy2(ipa_source_path, ipa_dest_path)  # ✅ 確保複製 IPA 時保留 Metadata
    print(f"✅ IPA 已複製到: {ipa_dest_path}")
    # 4️⃣ 🚀 設定解壓目錄
    unzip_dir = os.path.join(apple_ipa_dir, "unzip")  # ✅ 固定解壓目錄
    # 5️⃣ 🚀 刪除舊的解壓資料夾，確保新的解壓不會影響舊資料
    shutil.rmtree(unzip_dir, ignore_errors=True)
    # 6️⃣ 🚀 執行解壓
    run_subprocess(["unzip", "-q", ipa_dest_path, "-d", unzip_dir], "解壓 IPA 文件")
    print(f"✅ 已解壓 IPA 至: {unzip_dir}")
    return unzip_dir

def extract_entitlements(provisioning_profile_path, output_path):
    """🚀 從 Provisioning Profile (`.mobileprovision`) 提取 `Entitlements.plist`"""

    # 1️⃣ 🔍 確保檔案存在
    if not os.path.exists(provisioning_profile_path):
        print(f"❌ 描述文件不存在: {provisioning_profile_path}")
        raise FileNotFoundError(f"未找到 Provisioning Profile: {provisioning_profile_path}")

    try:
        # 2️⃣ 🚀 解析 Provisioning Profile (`security cms -D -i`)
        result = run_subprocess(
            ["security", "cms", "-D", "-i", provisioning_profile_path],
            "解析描述文件",
            stdout=subprocess.PIPE
        )
        # 3️⃣ 解析 Plist 資料
        plist_data = plistlib.loads(result.stdout.encode())
        entitlements = plist_data.get("Entitlements", {})
        if not entitlements:
            raise ValueError("❌ 未找到 `Entitlements` 欄位")
        # 4️⃣ ✅ 輸出到 `output_path`
        with open(output_path, "wb") as plist_file:
            plistlib.dump(entitlements, plist_file)

        print(f"✅ 已提取 Entitlements 至: {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ 提取 Entitlements 失敗: {e}")
        raise
    
def replace_provisioning_profile(unzip_dir, provisioning_profile_path):
    """🚀 替換 `.app` 內的 `embedded.mobileprovision`"""
    # 1️⃣ 🔍 確保 Provisioning Profile 存在
    if not os.path.exists(provisioning_profile_path):
        raise FileNotFoundError(f"❌ 描述文件不存在: {provisioning_profile_path}")
    # 2️⃣ 🔍 確保 Payload 資料夾存在
    app_path = os.path.join(unzip_dir, "Payload")
    if not os.path.exists(app_path):
        raise FileNotFoundError("❌ `Payload` 資料夾未找到，請檢查 IPA 結構是否正確。")
    # 3️⃣ 🔍 找到 `.app` 目錄
    app_dir = next(
        (os.path.join(app_path, item) for item in os.listdir(app_path) if item.endswith(".app")),
        None,
    )
    if not app_dir:
        raise FileNotFoundError("❌ 無法找到 `.app` 目錄，請檢查 IPA 結構。")

    # 4️⃣ 🚀 替換 `embedded.mobileprovision`
    embedded_profile_path = os.path.join(app_dir, "embedded.mobileprovision")
    shutil.copy(provisioning_profile_path, embedded_profile_path)
    print(f"✅ 已替換 `embedded.mobileprovision`: {embedded_profile_path}")
    return app_dir  # ✅ 回傳 `.app` 目錄

def remove_code_signature(app_dir):
    """刪除應用中的簽名"""
    code_signature_path = os.path.join(app_dir, "_CodeSignature")
    shutil.rmtree(code_signature_path, ignore_errors=True)
    
def sign_app(app_dir, signing_identity, entitlements_path):
    """簽名應用"""
    print(f"開始簽名應用：{app_dir}")
    keychain_path = os.path.expanduser(config.keychain_path)
    try:
        run_subprocess(
            [
                "codesign",
                "--force",
                "--sign", signing_identity,
                "--entitlements", entitlements_path,
                "--keychain", keychain_path,
                "--deep",
                app_dir,
            ],
            "簽名應用"
        )
        #log(f"已成功簽名應用：{app_dir}")
    except Exception as e:
        print(f"簽名失敗：{e}")
        raise

def repackage_ipa(unzip_dir):
    """🚀 重新打包 IPA 文件，並將其存放在 `unzip_dir` 的上層目錄"""
    
    parent_dir = os.path.dirname(unzip_dir)  # ✅ `unzip_dir` 的上層目錄
    resigned_ipa_path = os.path.join(parent_dir, "resigned.ipa")  # ✅ `_resigned.ipa` 存放在上層

    if os.path.exists(resigned_ipa_path):
        os.remove(resigned_ipa_path)

    payload_path = os.path.join(unzip_dir, "Payload")
    if not os.path.isdir(payload_path):
        raise FileNotFoundError(f"❌ Payload 資料夾未找到：{payload_path}")

    try:
        # 🚀 讓 zip 生成 `resigned.ipa` 在 `parent_dir` 下
        subprocess.run(
            ["zip", "-qr", resigned_ipa_path, "Payload"],
            cwd=unzip_dir,  # ✅ 確保 zip 在 `unzip_dir` 內執行
            check=True
        )
        print(f"✅ 已成功重新打包 IPA 文件：{resigned_ipa_path}")
        return resigned_ipa_path

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"❌ 重新打包 IPA 文件失敗：{e}")

def clean_up(unzip_dir):
    """清理臨時文件"""
    try:
        shutil.rmtree(unzip_dir, ignore_errors=True)
        print(f"已刪除解壓目錄：{unzip_dir}")
    except Exception as e:
        print(f"清理臨時文件失敗：{e}")

def resign_ipa(apple_id):
    """主流程：重簽 IPA 文件"""
    account = apple_accounts.get_account_by_apple_id(apple_id)
    if not account:
        print(f"❌ 找不到 Apple ID: {apple_id}，無法取得憑證")
        return False
    keychain.unlock_keychain()
    keychain.install_apple_wwdr_certificate()
    cert_id = account['cert_id']
    signing_identity = certificate.get_cer_sha1(cert_id)
    profile_path = os.path.join(config.profile_dir_path, f"adhoc_{cert_id}.mobileprovision")
    entitlements_path = None
    unzip_dir = None
    app_dir = None
    original_keychains = []
    try:
        # 記錄當前預設鑰匙圈
        result = subprocess.run(
            ["security", "list-keychains"], stdout=subprocess.PIPE, text=True, check=True
        )
        original_keychains = [
            keychain.strip().strip('"') for keychain in result.stdout.splitlines()
        ]
        keychain.configure_keychain_search()
        keychain.set_key_partition_list()
        # 解壓 IPA 文件
        unzip_dir = extract_ipa(account['apple_id'])
        # 定義固定路徑：entitlements.plist 和 app_dir
        entitlements_path = os.path.join(unzip_dir, "entitlements.plist")
        payload_dir = os.path.join(unzip_dir, "Payload")
        app_dir = next((os.path.join(payload_dir, item) for item in os.listdir(payload_dir) if item.endswith(".app")), None)
        # 驗證 Payload 和 .app 資料夾
        if not os.path.isdir(payload_dir):
            raise FileNotFoundError(f"未找到 Payload 資料夾：{payload_dir}")
        if not app_dir or not os.path.isdir(app_dir):
            raise FileNotFoundError(f"未找到 .app 資料夾：{app_dir}")
        # 提取 Entitlements 文件
        extract_entitlements(profile_path, entitlements_path)
        # 替換描述文件
        replace_provisioning_profile(unzip_dir, profile_path)
        # 移除舊簽名並重新簽名
        remove_code_signature(app_dir)
        sign_app(app_dir, signing_identity, entitlements_path)
        # 重新打包 IPA
        resigned_ipa_path = repackage_ipa(unzip_dir)
        print(f"重簽名流程完成！ 位置: {resigned_ipa_path}")
        return resigned_ipa_path
    except Exception as e:
        print(f"重簽名失敗：{e}")
        raise
    finally:
        keychain.restore_default_keychain(original_keychains)
        clean_up(unzip_dir)
        
def resign_single_account(account):
    """🔄 針對單一 Apple ID 執行 IPA 重簽名"""
    apple_id = account["apple_id"]
    try:
        print(f"🚀 開始重簽名 Apple ID: {apple_id}")
        result = resign_ipa(apple_id)
        if result:
            print(f"✅ Apple ID {apple_id} 簽名成功：{result}")
        else:
            print(f"❌ Apple ID {apple_id} 簽名失敗")
    except Exception as e:
        print(f"❌ Apple ID {apple_id} 簽名時發生錯誤：{e}")
        
def batch_resign_all_accounts(max_workers=10):
    """🚀 讀取所有 Apple 帳號，並行執行重簽名"""
    accounts = apple_accounts.get_accounts()  # ✅ 從資料庫讀取所有帳戶
    if not accounts:
        print("⚠️ 沒有找到可用的 Apple 帳號")
        return

    print(f"🚀 開始批量重簽名，最大並行數: {max_workers}")
    
    # ✅ 使用 ThreadPoolExecutor 進行並行簽名
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(resign_single_account, accounts)
        