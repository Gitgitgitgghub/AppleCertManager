# 🍏 AppleCertManager

Apple 開發者帳號 & 憑證管理工具

AppleCertManager 是一個 **CLI 工具**，用於**管理 Apple 開發者帳號、憑證、設備註冊，以及批量 IPA 重新簽名**。

## 🚀 安裝

### 1️⃣ 環境需求

- Python **3.9+**
- macOS（需安裝 `security` 命令）
- `pip`（Python 套件管理工具）
- `fastlane`（用於管理 Apple 憑證）

### 2️⃣ 安裝相依套件

```bash
pip install -r requirements.txt
```

### 3️⃣ 建立 `.env` 配置

請根據需求建立**不同環境的** `.env` 檔案，例如：

```ini
# 📌📌📌 專案根目錄（統一管理所有路徑）📌📌📌
ROOT_DIR="${HOME}/Desktop/test1"

# 📌📌📌 BUNDLE_ID 📌📌📌
BUNDLE_ID="com.example"

# 📌 macOS Keychain 設定
KEYCHAIN_PATH="${HOME}/Library/Keychains/Certs.keychain-db"

# 📌 macOS Keychain 鑰匙圈密碼 ❌最好純數字，不知道為啥非純數字會導致解鎖失敗導致一直詢問你密碼
KEYCHAIN_PASSWORD="password" 


#-----------------------------------------------#

# 📌 Apple portal 申請來的.p8位置
API_KEY_DIR_PATH="${ROOT_DIR}/api_key"

# 📌 資料庫
DB_PATH="${ROOT_DIR}/apple_account.sqlite"

# 📌 憑證 & Provisioning Profile
CERT_DIR_PATH="${ROOT_DIR}/certs"
PROFILE_DIR_PATH="${ROOT_DIR}/profiles"

# 📌 IPA 輸出路徑
IPA_DIR_PATH="${ROOT_DIR}/ipa"
# 📌 IPA 原始檔案路徑
IPA_PATH="${ROOT_DIR}/app.ipa"

# 📌 批次匯入檔案的json位置
JSON_PATH="${ROOT_DIR}/accounts.json"
```
❌鑰匙圈密碼最好純數字，不知道為啥非純數字會導致解鎖失敗導致一直詢問你密碼
目前規劃的是一個專案對應一個.env檔案，所以ROOT_DIR可以設置不同資料夾
理論上只有

- 1.ROOT_DIR
- 2.BUNDLE_ID
- 3.KEYCHAIN_PATH (如果不想要所有憑證都塞在同一個鑰匙圈可以改)

需要注意一下，還有ipa位置配置看下面第四點

### 4️⃣ 配置ipa位置

重簽名後的ipa會放在以下位置
```ini
IPA_DIR_PATH="${ROOT_DIR}/ipa"
```
要重簽名的ipa位置
```ini
IPA_PATH="${ROOT_DIR}/app.ipa"
```
.env 配置需要和上面對的上

## 🔧 使用方式

所有指令透過 `cli.py` 操作，並且**強制指定** `.env` 檔案，確保環境變數正確載入。

## 📌 指令總覽

| 指令 | 說明 |
|------|------|
| `query` | 查詢 Apple ID |
| `add` | 新增 Apple ID |
| `delete` | 刪除 Apple ID |
| `import` | 批量匯入 Apple ID |
| `register_device` | 註冊新設備 |
| `resign` | 重新簽名 IPA |
| `revoke_cert` | 撤銷 Apple ID 憑證 |
| `revoke_expired_cert` | 自動撤銷過期憑證 |

## 📜 使用說明

### 1️⃣ Apple ID 管理

#### 📋 查詢 Apple ID 列表

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env query
```

#### ➕ 新增 Apple ID

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env add test@example.com ISSUER_ID KEY_ID
```

#### 🗑 刪除 Apple ID

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env delete test@example.com
```

#### 📂 批量匯入 Apple ID

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env import --json /Users/brant/Desktop/fastlane/accounts.json
```

##### 📌 JSON 檔案格式

```json
[
  {
    "apple_id": "test@example.com",
    "issuer_id": "ISSUER_ID",
    "key_id": "KEY_ID"
  }
]
```

### 📱 設備管理

#### 📲 註冊新設備

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env register_device test@example.com "iPhone 14" "UUID123"
```

### 🔄 IPA 重新簽名

#### 🚀 執行重新簽名

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env resign hello780831@example.com
```

##### 📌 說明
* 這個指令會**Apple ID 執行 IPA 重新簽名**
* 確保 Apple ID 已經有**有效的憑證**和**描述檔**

### 🔄 批量 IPA 重新簽名

#### 🚀 執行批量重新簽名

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env resign
```

##### 📌 說明
* 這個指令會**針對所有 Apple ID 執行 IPA 重新簽名**
* 確保 Apple ID 已經有**有效的憑證**和**描述檔**

### 🛑 憑證管理

#### 🔍 自動撤銷過期憑證

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env revoke_expired_cert
```

##### 📌 說明
* 這個指令會檢查**所有 Apple ID 的憑證**，並自動刪除已經**過期的憑證**

#### ❌ 手動撤銷 Apple ID 憑證

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env revoke_cert test@example.com
```

##### 📌 說明
* 這個指令會列出該 Apple ID **目前的所有憑證**，讓你選擇要刪除的憑證

## 💡 常見問題

### 1️⃣ `ModuleNotFoundError: No module named 'apple_cert_manager'`

**解法：** 請確保你在**專案根目錄**執行：

```bash
cd /Users/brant/Desktop/AppleCertManager
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env query
```

### 2️⃣ `AttributeError: 'NoneType' object has no attribute 'db_path'`

**解法：** 這通常是因為 `.env` **沒有正確載入**，請確保：
* `.env` 檔案存在且路徑正確
* 指令有**指定** `--env`

你可以**手動檢查** `.env` 是否載入：

```bash
python3 scripts/cli.py --env /Users/brant/Desktop/test1/.env query
```

如果 `.env` 成功載入，你應該會看到：

```bash
✅ .env 已載入: /Users/brant/Desktop/test1/.env
🔍 db_path: /Users/brant/Desktop/test1/apple_account.sqlite
```

