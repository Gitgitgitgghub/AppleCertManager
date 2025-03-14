# http_client.py
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日誌
logging.basicConfig(level=logging.INFO)

class HttpClient:
    """封裝帶有重試和超時的 HTTP 客戶端"""
    def __init__(self, timeout=10, retries=3, backoff_factor=1):
        """
        初始化 HTTP 客戶端。
        
        Args:
            timeout (int): 每個請求的超時時間（秒），預設 10 秒。
            retries (int): 最大重試次數，預設 3 次。
            backoff_factor (float): 重試間隔的增長因子，預設 1（秒）。
        """
        self.session = requests.Session()
        self.timeout = timeout
        
        # 配置重試策略
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],  # 重試的狀態碼
            allowed_methods=["GET", "POST", "DELETE", "PUT"]  # 支持的重試方法
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(self, url, headers=None, **kwargs):
        """發送 GET 請求"""
        try:
            response = self.session.get(url, headers=headers, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.error(f"GET 請求失敗: {url}, 錯誤: {e}")
            raise

    def post(self, url, headers=None, data=None, json=None, **kwargs):
        """發送 POST 請求"""
        try:
            response = self.session.post(url, headers=headers, data=data, json=json, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.error(f"POST 請求失敗: {url}, 錯誤: {e}")
            raise

    def delete(self, url, headers=None, **kwargs):
        """發送 DELETE 請求"""
        try:
            response = self.session.delete(url, headers=headers, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.error(f"DELETE 請求失敗: {url}, 錯誤: {e}")
            raise

    def put(self, url, headers=None, data=None, json=None, **kwargs):
        """發送 PUT 請求"""
        try:
            response = self.session.put(url, headers=headers, data=data, json=json, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.error(f"PUT 請求失敗: {url}, 錯誤: {e}")
            raise

# 創建單例客戶端
http_client = HttpClient(timeout=10, retries=3, backoff_factor=1)