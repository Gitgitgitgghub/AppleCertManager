from . import profile
from . import resign_ipa
import logging

logging = logging.getLogger(__name__)

def register_device_and_resign(apple_id, device_name, device_udid):
    """註冊新設備並且更新本地的profile後重簽名"""
    try:
        profile.register_device(apple_id, device_name, device_udid)
        profile.get_provisioning_profile(apple_id)
        resign_ipa.resign_ipa(apple_id)
    except Exception as e:
        logging.error(f"註冊新裝置重簽名失敗: {e}")