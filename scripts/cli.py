import argparse
from apple_cert_manager.config import config

def load_modules():
    """📌 動態加載模組，確保 `.env` 先載入"""
    global insert_account, delete_account, query_accounts, insert_from_json
    global register_device
    global resign_ipa, batch_resign_all_accounts
    global revoke_expired_certificates, revoke_certificate

    from apple_cert_manager.apple_accounts import (
        insert_account,
        delete_account,
        query_accounts,
        insert_from_json,
    )
    from apple_cert_manager.profile import register_device
    from apple_cert_manager.resign_ipa import resign_ipa, batch_resign_all_accounts
    from apple_cert_manager.revoke_expired_cert import revoke_expired_certificates, revoke_certificate

def main():
    parser = argparse.ArgumentParser(description="🔧 Apple 開發者帳號與憑證管理工具")
    
    # ✅ **強制要求 `.env`**
    parser.add_argument(
        "--env", type=str, required=True, help="⚠️ 必須指定 `.env` 檔案"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用指令")

    # 🎯 **帳號管理**
    parser_add = subparsers.add_parser("add", help="🚀 新增 Apple ID")
    parser_add.add_argument("apple_id", help="Apple ID (Email)")
    parser_add.add_argument("issuer_id", help="Issuer ID")
    parser_add.add_argument("key_id", help="Key ID")

    parser_delete = subparsers.add_parser("delete", help="🗑 刪除 Apple ID")
    parser_delete.add_argument("apple_id", help="Apple ID (Email)")

    subparsers.add_parser("query", help="📜 查詢所有 Apple 帳號")

    parser_import = subparsers.add_parser("import", help="📂 批量匯入 JSON")
    parser_import.add_argument(
        "--json", type=str, default=None, help="指定 JSON 檔案 (預設為 config.json_path)"
    )

    # 🎯 **設備管理**
    parser_register_device = subparsers.add_parser("register_device", help="📱 註冊新設備")
    parser_register_device.add_argument("apple_id", help="Apple ID (Email)")
    parser_register_device.add_argument("name", help="設備名稱")
    parser_register_device.add_argument("uuid", help="設備 UUID")

    # 🎯 **重新簽名**
    subparsers.add_parser("resign", help="🔄 使用所有帳號重簽 IPA")

    # 🎯 **憑證管理**
    parser_revoke_expired_cert = subparsers.add_parser("revoke_expired_cert", help="🗑 刪除所有帳號過期的發佈憑證")
    parser_revoke_cert = subparsers.add_parser("revoke_cert", help="🗑 刪除指定 Apple ID 的憑證")
    parser_revoke_cert.add_argument("apple_id", help="Apple ID (Email)")

    args = parser.parse_args()

    # 🚀 **先載入 `.env`**
    config.load(args.env)
    
    # 📌 **動態加載模組**
    load_modules()

    # 🛠 **執行對應的指令**
    if args.command == "add":
        insert_account(args.apple_id, args.issuer_id, args.key_id)

    elif args.command == "delete":
        delete_account(args.apple_id)

    elif args.command == "query":
        print(f"✅ .env 已載入: {args.env}")
        print(f"🔍 db_path: {config.db_path}")
        query_accounts()

    elif args.command == "import":
        json_path = args.json or config.json_path
        insert_from_json(json_path)

    elif args.command == "register_device":
        result = register_device(args.apple_id, args.name, args.uuid)
        if result:
            resign_ipa(args.apple_id)

    elif args.command == "resign":
        batch_resign_all_accounts()

    elif args.command == "revoke_expired_cert":
        revoke_expired_certificates()

    elif args.command == "revoke_cert":
        revoke_certificate(args.apple_id)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
