import apple_accounts
import certificate
import profile
import local_file



def match_apple_account(apple_id):
    """ 設定這個apple帳號的憑證與profile """
    account = apple_accounts.get_account_by_apple_id(apple_id)
    print(f"✅ 開始設定 Apple ID: {apple_id} 憑證與profile")
    if not account:
        print(f"❌ 找不到 Apple ID: {apple_id}，無法取得憑證")
        return False
    # 檢查該帳號是否有超過２張distribution憑證，有的話刪除最舊的
    removed_cert_id = certificate.revoke_oldest_distribution_certificate(apple_id)
    if removed_cert_id:
        certificate.remove_keychain_certificate_by_id(removed_cert_id)
        local_file.remove_local_files(removed_cert_id)
    else:
        print(f"✅ 並無需要刪除的憑證")
    cert_id = certificate.create_distribution_certificate(apple_id)
    if cert_id:
        apple_accounts.update_cert_id(apple_id, cert_id)
        profile.get_provisioning_profile(apple_id)
        print(f"✅ 已建立帳號: {apple_id} 新的憑證與profile檔案")
    else:
        print(f"❌憑證建立失敗")