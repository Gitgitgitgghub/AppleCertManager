
# echo 'export PYTHONPATH="/Users/brant/Desktop/AppleCertManager"' >> ~/.zshrc
# source ~/.zshrc  # 讓修改生效

from apple_cert_manager.logging_config import configure_logging
import logging
# # 配置日誌系統
configure_logging()