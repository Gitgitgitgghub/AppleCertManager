from datetime import datetime
from . import certificate
from apple_cert_manager.config import config 
from . import apple_accounts 
from . import match
from . import local_file

def is_certificate_expired(expiration_date):
    """ 檢查憑證是否過期 """
    try:
        exp_date = datetime.strptime(expiration_date, "%Y-%m-%dT%H:%M:%S.%f%z")
        return exp_date < datetime.now(exp_date.tzinfo)
    except Exception as e:
        print(f"解析日期錯誤: {e}")
        return False
    #return True


def revoke_expired_certificates():
    """ 遍歷 SQLite 資料庫，處理所有帳戶的過期憑證（僅刪除 distribution 類型） """
    accounts = apple_accounts.get_accounts()  #** 從SQLite讀取帳戶 **
    # try:
    #     import cert  # 🚀 嘗試 import `cert`
    #     print("✅ `cert` 成功導入")
    # except ImportError as e:
    #     print(f"❌ `cert` 無法導入，錯誤訊息: {e}")
    for account in accounts:
        issuer_id = account["issuer_id"]
        api_key_id = account["key_id"]
        apple_id = account['apple_id']
        print(f"正在處理 Apple ID: {apple_id}")
        certificates = certificate.list_certificates(apple_id)
        if not certificates:
            print("沒有找到憑證，跳過")
            continue
        # **過濾過期且類型為 `distribution` 的憑證**
        expired_certificates = [
            cert for cert in certificates
            if is_certificate_expired(cert['attributes']['expirationDate']) and
            cert['attributes']['certificateType'] in ["DISTRIBUTION", "IOS_DISTRIBUTION"]
        ]

        if not expired_certificates:
            print("沒有符合條件的過期 Distribution 憑證，跳過")
            continue

        print(f"找到 {len(expired_certificates)} 個過期 Distribution 憑證，開始刪除...")
        deleted_certificates = []  # **存放成功刪除的憑證**
        for cert in expired_certificates:
            cert_id = cert['id']
            print(f"🚨 刪除過期 `DISTRIBUTION` 憑證 ID: {cert_id}...")
            if certificate.revoke_certificate(apple_id, cert_id):
                deleted_certificates.append(cert)  # **紀錄成功刪除的憑證**
            else:
                print(f"❌ 刪除憑證 {cert_id} 失敗，跳過")

        # **移除 macOS 本地憑證**
        for cert in deleted_certificates:
            certificate.remove_keychain_certificate(cert)
            local_file.remove_local_files(apple_id)
        
        # 如果有被刪除的憑證要重新match
        if deleted_certificates:
            apple_accounts.clear_cert_id(apple_id)
            match.match_apple_account(apple_id)
    print(f"✅  刪除所有過期憑證成功")

def revoke_certificate(apple_id):
    """刪除指定的證書"""
    certificates = certificate.list_certificates(apple_id)
    # 🔍 **如果沒有憑證，直接回報錯誤**
    if not certificates:
        print(f"⚠️ Apple ID `{apple_id}` 沒有可撤銷的憑證")
        return
    # 🚀 **提示輸入憑證 ID**
    while True:
        cert_id = input("\n請輸入要刪除的證書 ID: ").strip()
        
        # ✅ **檢查是否為有效的證書 ID**
        cert_to_revoke = next((cert for cert in certificates if cert["id"] == cert_id), None)
        
        if cert_to_revoke:
            break  # 找到證書，退出迴圈
        else:
            print("❌ 無效的證書 ID，請重新輸入")
    
    print(f"開始撤銷憑證: {cert_id}...")
    
    # 🚀 **調用撤銷函數**
    if certificate.revoke_certificate(apple_id, cert_id):
        certificate.remove_keychain_certificate(cert_to_revoke)
        local_file.remove_local_files(apple_id)
        print(f"✅ 成功撤銷憑證 {cert_id}")
    else:
        print(f"❌ 撤銷憑證 {cert_id} 失敗")

