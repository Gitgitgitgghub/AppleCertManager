import subprocess
import os
import shutil
import plistlib
import logging
import concurrent.futures
from rich.progress import Progress
from apple_cert_manager.config import config
from . import apple_accounts
from . import keychain
from . import certificate

def extract_ipa(apple_ipa_dir, ipa_dest_path, unzip_dir):
    os.makedirs(apple_ipa_dir, exist_ok=True)
    shutil.copy2(config.ipa_path, ipa_dest_path)
    shutil.rmtree(unzip_dir, ignore_errors=True)
    try:
        subprocess.run(["unzip", "-q", ipa_dest_path, "-d", unzip_dir], check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"解壓 IPA 文件失敗: {e.stderr or e.stdout or str(e)}")
        raise
    return unzip_dir

def get_app_dir(unzip_dir):
    payload_path = os.path.join(unzip_dir, "Payload")
    app_dir = next(
        (os.path.join(payload_path, item) for item in os.listdir(payload_path) if item.endswith(".app")),
        None
    )
    if not app_dir:
        raise FileNotFoundError("無法找到 .app 目錄")
    return app_dir

def replace_bundle_id(app_dir, new_bundle_id):
    info_plist_path = os.path.join(app_dir, "Info.plist")
    with open(info_plist_path, "rb") as f:
        info_plist = plistlib.load(f)
    old_bundle_id = info_plist.get("CFBundleIdentifier", "")
    if old_bundle_id != new_bundle_id:
        info_plist["CFBundleIdentifier"] = new_bundle_id
        with open(info_plist_path, "wb") as f:
            plistlib.dump(info_plist, f)
        logging.info(f"已將 Bundle ID 從 {old_bundle_id} 替換為 {new_bundle_id}")
    return new_bundle_id

def extract_entitlements(provisioning_profile_path, entitlements_path):
    try:
        output = subprocess.run(
            ["security", "cms", "-D", "-i", provisioning_profile_path],
            check=True, text=True, capture_output=True
        ).stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"解析描述文件失敗: {e.stderr or e.stdout or str(e)}")
        raise
    plist_data = plistlib.loads(output.encode())
    entitlements = plist_data.get("Entitlements", {})
    with open(entitlements_path, "wb") as plist_file:
        plistlib.dump(entitlements, plist_file)
    logging.info(f"已提取 Entitlements 至: {entitlements_path}")
    return entitlements_path

def replace_provisioning_profile(unzip_dir, provisioning_profile_path):
    app_dir = get_app_dir(unzip_dir)
    embedded_profile_path = os.path.join(app_dir, "embedded.mobileprovision")
    shutil.copy(provisioning_profile_path, embedded_profile_path)
    logging.info(f"已替換 embedded.mobileprovision: {embedded_profile_path}")
    return app_dir

def remove_code_signature(app_dir):
    code_signature_path = os.path.join(app_dir, "_CodeSignature")
    if os.path.exists(code_signature_path):
        shutil.rmtree(code_signature_path)
        logging.info(f"已移除舊簽名: {code_signature_path}")

def sign_app(app_dir, signing_identity, entitlements_path, keychain_path):
    # 簽名嵌套應用和擴展
    for root, dirs, _ in os.walk(app_dir):
        for d in dirs:
            if d.endswith((".app", ".appex")):
                nested_path = os.path.join(root, d)
                #logging.info(f"簽名嵌套應用: {nested_path}")
                sign_single_app(nested_path, signing_identity, entitlements_path, keychain_path)

    # 簽名框架和動態庫
    frameworks_dir = os.path.join(app_dir, "Frameworks")
    if os.path.exists(frameworks_dir):
        for item in os.listdir(frameworks_dir):
            if item.endswith((".framework", ".dylib")):
                framework_path = os.path.join(frameworks_dir, item)
                #logging.info(f"簽名框架: {framework_path}")
                try:
                    subprocess.run([
                        "codesign", "--force", "--sign", signing_identity,
                        "--keychain", keychain_path, "--generate-entitlement-der",
                        framework_path
                    ], check=True, text=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    logging.error(f"簽名框架失敗: {framework_path}: {e.stderr or e.stdout or str(e)}")
                    raise

    # 簽名 OnDemandResources
    odr_dir = os.path.join(os.path.dirname(app_dir), "OnDemandResources")
    if os.path.exists(odr_dir):
        for item in os.listdir(odr_dir):
            if item.endswith(".assetpack"):
                assetpack_path = os.path.join(odr_dir, item)
                remove_code_signature(assetpack_path)
                #logging.info(f"簽名 OnDemandResource: {assetpack_path}")
                try:
                    subprocess.run([
                        "codesign", "--force", "--sign", signing_identity,
                        "--keychain", keychain_path, "--generate-entitlement-der",
                        assetpack_path
                    ], check=True, text=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    logging.error(f"簽名 OnDemandResource 失敗: {assetpack_path}: {e.stderr or e.stdout or str(e)}")
                    raise

    # 簽名主應用
    sign_single_app(app_dir, signing_identity, entitlements_path, keychain_path)

def sign_single_app(app_path, signing_identity, entitlements_path, keychain_path):
    command = [
        "codesign", "--force", "--sign", signing_identity,
        "--entitlements", entitlements_path, "--keychain", keychain_path,
        "--generate-entitlement-der", "--timestamp", "--options", "runtime",
        app_path
    ]
    try:
        subprocess.run(command, check=True, text=True, capture_output=True)
        logging.info(f"已成功簽名應用: {app_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"簽名應用失敗: {app_path}: {e.stderr or e.stdout or str(e)}")
        raise

def repackage_ipa(unzip_dir, resigned_ipa_path):
    if os.path.exists(resigned_ipa_path):
        os.remove(resigned_ipa_path)
    try:
        subprocess.run(["zip", "-qr", resigned_ipa_path, "Payload"], cwd=unzip_dir, check=True, text=True, capture_output=True)
        #logging.info(f"已成功重新打包 IPA 文件: {resigned_ipa_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"重新打包 IPA 文件失敗: {e.stderr or e.stdout or str(e)}")
        raise
    return resigned_ipa_path

def clean_up(unzip_dir, copy_ipa_path):
    if os.path.exists(unzip_dir):
        shutil.rmtree(unzip_dir)
    if os.path.exists(copy_ipa_path):
        os.remove(copy_ipa_path)

def validate_signing_identity(signing_identity):
    try:
        output = subprocess.run(
            ["security", "find-identity", "-v", "-p", "codesigning"],
            check=True, text=True, capture_output=True
        ).stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"無法驗證簽名身份: {e.stderr or e.stdout or str(e)}")
        raise
    if signing_identity not in output:
        raise ValueError(f"簽名身份無效或不在鑰匙圈中: {signing_identity}")
    logging.info(f"簽名身份驗證通過: {signing_identity}")

def resign_ipa(apple_id):
    account = apple_accounts.get_account_by_apple_id(apple_id)
    apple_id_prefix = apple_id.split("@")[0]
    apple_ipa_dir = os.path.join(config.ipa_dir_path, apple_id_prefix)
    ipa_dest_path = os.path.join(apple_ipa_dir, os.path.basename(config.ipa_path))
    unzip_dir = os.path.join(apple_ipa_dir, "unzip")
    cert_id = account['cert_id']
    profile_path = os.path.join(config.profile_dir_path, f"adhoc_{cert_id}.mobileprovision")
    entitlements_path = os.path.join(unzip_dir, "entitlements.plist")
    keychain_path = os.path.expanduser(config.keychain_path)
    resigned_ipa_path = os.path.join(apple_ipa_dir, "resigned.ipa")
    
    signing_identity = certificate.get_cer_sha1(cert_id)
    validate_signing_identity(signing_identity)
    
    try:
        output = subprocess.run(["security", "list-keychains"], check=True, text=True, capture_output=True).stdout
        original_keychains = [kc.strip().strip('"') for kc in output.splitlines()]
    except subprocess.CalledProcessError as e:
        logging.error(f"獲取鑰匙圈列表失敗: {e.stderr or e.stdout or str(e)}")
        raise
    
    try:
        keychain.unlock_keychain()
        keychain.install_apple_wwdr_certificate()
        keychain.configure_keychain_search()
        keychain.set_key_partition_list()
        
        extract_ipa(apple_ipa_dir, ipa_dest_path, unzip_dir)
        app_dir = get_app_dir(unzip_dir)
        new_bundle_id = config.bundle_id  # 假設從 config 中獲取
        replace_bundle_id(app_dir, new_bundle_id)
        replace_provisioning_profile(unzip_dir, profile_path)
        extract_entitlements(profile_path, entitlements_path)
        remove_code_signature(app_dir)
        sign_app(app_dir, signing_identity, entitlements_path, keychain_path)
        repackage_ipa(unzip_dir, resigned_ipa_path)
        return resigned_ipa_path
    except Exception as e:
        logging.error(f"重簽名失敗: {e}")
        raise
    finally:
        keychain.restore_default_keychain(original_keychains)
        clean_up(unzip_dir, ipa_dest_path)

def resign_single_account(account):
    apple_id = account["apple_id"]
    logging.info(f"開始重簽名 Apple ID: {apple_id}")
    try:
        result = resign_ipa(apple_id)
        logging.info(f"Apple ID {apple_id} 簽名成功: {result}")
        return apple_id, result
    except Exception as e:
        logging.error(f"Apple ID {apple_id} 簽名失敗: {e}")
        return apple_id, None

def batch_resign_all_accounts(max_workers=min(os.cpu_count() or 1, 10)):
    accounts = apple_accounts.get_accounts()
    logging.info(f"開始批量重簽名，最大並行數: {max_workers}")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_account = {executor.submit(resign_single_account, acc): acc for acc in accounts}
        for future in concurrent.futures.as_completed(future_to_account):
            results.append(future.result())
    with Progress() as progress:
        task_id = progress.add_task("[green]批量重簽名", total=len(accounts))
        for _ in results:
            progress.update(task_id, advance=1)
