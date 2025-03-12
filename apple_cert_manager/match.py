from . import apple_accounts
from . import certificate
from . import profile
from . import local_file



def match_apple_account(apple_id):
    """ 設定這個apple帳號的憑證與profile """
    account = apple_accounts.get_account_by_apple_id(apple_id)
    print(f"🔍 開始設定 Apple ID: {apple_id} 憑證與profile")
    if not account:
        print(f"❌ 找不到 Apple ID: {apple_id}，無法取得憑證")
        return False
    cert_id = certificate.create_certificate(apple_id)
    if cert_id:
        apple_accounts.update_cert_id(apple_id, cert_id)
        print(f"✅ 已建立帳號: {apple_id} 新的憑證✅")
    else:
        print(f"❌憑證建立失敗 appleID: {apple_id}")
        raise
    get_profile = profile.get_provisioning_profile(apple_id)
    if get_profile:
        print(f"✅ 已建立帳號: {apple_id} 新的profile檔案✅")
    else:
        print(f"❌描述檔建立失敗 appleID: {apple_id}")
        raise
    print(f"✅✅✅ 已建立帳號: {apple_id} 新的憑證與profile檔案✅✅✅")