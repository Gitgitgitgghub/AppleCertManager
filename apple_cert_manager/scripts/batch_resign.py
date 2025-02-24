import concurrent.futures
import sys
import os
# 確保可以找到 `apple_cert_manager/`
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from apple_cert_manager.apple_accounts import get_accounts
from apple_cert_manager.resign_ipa import resign_ipa

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
    accounts = get_accounts()  # ✅ 從資料庫讀取所有帳戶
    if not accounts:
        print("⚠️ 沒有找到可用的 Apple 帳號")
        return

    print(f"🚀 開始批量重簽名，最大並行數: {max_workers}")
    
    # ✅ 使用 ThreadPoolExecutor 進行並行簽名
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(resign_single_account, accounts)

if __name__ == "__main__":
    batch_resign_all_accounts(max_workers=4)  # ✅ 預設最多 4 個並行任務
