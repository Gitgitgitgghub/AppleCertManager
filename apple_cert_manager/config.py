import os
from dotenv import load_dotenv

class Config:
    """ 📌 動態讀取 `.env` 並提供存取設定的方式 """

    def __init__(self):
        self.env_loaded = False
        self.load_called = False  # ✅ 確保 `.env` 只會載入一次
        self.root_dir = None
        self.api_key_dir_path = None
        self.db_path = None
        self.cert_dir_path = None
        self.profile_dir_path = None
        self.ipa_path = None
        self.ipa_dir_path = None
        self.json_path = None
        self.keychain_path = None
        self.keychain_password = None
        self.bundle_id = None

    def load(self, env_path):
        """ 🚀 載入 `.env` 環境變數 """
        if self.load_called:
            print("⚠️ `config.load()` 已經執行過，跳過重複載入")
            return
        
        if not os.path.exists(env_path):
            raise FileNotFoundError(f"❌ 找不到 `.env` 檔案: {env_path}")

        load_dotenv(env_path)
        print(f"✅ `.env` 已載入: {env_path}")

        # 📌 **讀取 `.env` 變數**
        self.root_dir = os.getenv("ROOT_DIR")
        self.api_key_dir_path = os.getenv("API_KEY_DIR_PATH")
        self.db_path = os.getenv("DB_PATH")
        self.cert_dir_path = os.getenv("CERT_DIR_PATH")
        self.profile_dir_path = os.getenv("PROFILE_DIR_PATH")
        self.ipa_dir_path = os.getenv("IPA_DIR_PATH")
        self.ipa_path = os.getenv("IPA_PATH")
        self.json_path = os.getenv("JSON_PATH")
        self.keychain_path = os.getenv("KEYCHAIN_PATH")
        self.keychain_password = os.getenv("KEYCHAIN_PASSWORD")
        self.bundle_id = os.getenv("BUNDLE_ID")

        # ✅ **確保環境變數已載入**
        self.env_loaded = True
        self.load_called = True
        
        # 📁 **檢查並建立必要資料夾**
        dirs_to_check = {
            "cert_dir_path": self.cert_dir_path,
            "profile_dir_path": self.profile_dir_path,
            "ipa_dir_path": self.ipa_dir_path
        }

        for dir_name, dir_path in dirs_to_check.items():
            if dir_path:  # 確保路徑不為 None 或空字串
                if not os.path.exists(dir_path):
                    try:
                        os.makedirs(dir_path, exist_ok=True)
                        print(f"📂 已建立資料夾: {dir_path}")
                    except OSError as e:
                        print(f"❌ 無法建立資料夾 {dir_name}: {dir_path}, 錯誤: {e}")
                        raise  
            else:
                print(f"⚠️ {dir_name} 未設定或為空，跳過建立")

# 🚀 **創建 `config` 實例**
config = Config()
