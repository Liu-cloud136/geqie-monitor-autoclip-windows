#!/usr/bin/env python3
"""
简单同步HTTP客户端，作为aiohttp的fallback
"""
import requests
import logging
import time
from typing import Optional, Dict, Any

class SimpleHTTPClient:
    """简单同步HTTP客户端 - 不使用异步"""
    
    def __init__(self):
        self.session = requests.Session()
        # 设置默认请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def get(self, url: str, headers: Dict = None, timeout: int = 15) -> Optional[Dict]:
        """
        同步GET请求
        
        Args:
            url: 请求URL
            headers: 请求头
            timeout: 超时时间（秒）
        
        Returns:
            响应JSON数据，失败返回None
        """
        try:
            response_headers = self.session.headers.copy()
            if headers:
                response_headers.update(headers)
            
            response = self.session.get(url, headers=response_headers, timeout=timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logging.warning(f"HTTP请求失败 {response.status_code}: {url}")
                return None
                
        except requests.exceptions.Timeout:
            logging.warning(f"请求超时: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"HTTP请求失败: {url} - {e}")
            return None
        except Exception as e:
            logging.warning(f"请求异常: {url} - {e}")
            return None

# 全局简单HTTP客户端实例
simple_http_client = SimpleHTTPClient()