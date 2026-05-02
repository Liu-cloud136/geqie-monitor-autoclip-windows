#!/usr/bin/env python3
"""
B站直播流获取 API
- 获取直播流地址
- 支持多种画质选择
- 支持自动重试和备用链接
"""

import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logging.warning("httpx 未安装，直播流获取功能将受限")


class StreamQuality(Enum):
    """直播流画质"""
    ORIGIN = "原画"
    FOUR_K = "4K"
    TWO_K = "2K"
    FULL_HD = "1080P"
    HD = "720P"
    SD = "480P"
    LD = "360P"
    AUTO = "自动"


@dataclass
class StreamUrl:
    """直播流地址"""
    url: str
    quality: str
    codec: Optional[str] = None
    format: str = "flv"
    priority: int = 0


@dataclass
class LiveStreamInfo:
    """直播流信息"""
    room_id: int
    is_live: bool
    title: str
    stream_urls: List[StreamUrl] = field(default_factory=list)
    liver_name: str = ""
    area_name: str = ""
    cover_url: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def get_best_quality_url(self) -> Optional[StreamUrl]:
        """获取最高画质的流地址"""
        if not self.stream_urls:
            return None
        
        quality_order = {
            "4K": 10,
            "2K": 9,
            "原画": 8,
            "1080P": 7,
            "720P": 6,
            "480P": 5,
            "360P": 4,
            "自动": 1
        }
        
        sorted_urls = sorted(
            self.stream_urls,
            key=lambda x: (
                quality_order.get(x.quality, 0),
                x.priority
            ),
            reverse=True
        )
        return sorted_urls[0] if sorted_urls else None
    
    def get_url_by_quality(self, quality: str) -> Optional[StreamUrl]:
        """根据画质获取流地址"""
        for url in self.stream_urls:
            if url.quality == quality:
                return url
        return None


class BilibiliLiveStreamAPI:
    """B站直播流API"""
    
    def __init__(self, 
                 headers: Dict[str, str] = None,
                 credential: Dict[str, str] = None,
                 timeout: int = 15):
        
        self.timeout = timeout
        self.credential = credential or {}
        
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://live.bilibili.com",
            "Origin": "https://live.bilibili.com"
        }
        
        if headers:
            self.default_headers.update(headers)
        
        self._session: Optional[httpx.AsyncClient] = None
        
        self.api_room_init = "https://api.live.bilibili.com/room/v1/Room/room_init?id={room_id}"
        self.api_room_info = "https://api.live.bilibili.com/room/v1/Room/get_info?id={room_id}"
        self.api_play_url = "https://api.live.bilibili.com/room/v1/Room/playUrl?cid={room_id}&qn={qn}&platform=web"
        
        self.quality_qn_map = {
            "原画": 10000,
            "4K": 20000,
            "2K": 10000,
            "1080P": 1080,
            "720P": 720,
            "480P": 480,
            "360P": 360,
            "自动": 0
        }
    
    def _get_headers(self, room_id: int = None) -> Dict[str, str]:
        """获取请求头"""
        headers = self.default_headers.copy()
        
        if room_id:
            headers["Referer"] = f"https://live.bilibili.com/{room_id}"
        
        if self.credential.get('sessdata'):
            cookie_parts = []
            if self.credential.get('sessdata'):
                cookie_parts.append(f"SESSDATA={self.credential['sessdata']}")
            if self.credential.get('bili_jct'):
                cookie_parts.append(f"bili_jct={self.credential['bili_jct']}")
            if self.credential.get('buvid3'):
                cookie_parts.append(f"buvid3={self.credential['buvid3']}")
            headers["Cookie"] = "; ".join(cookie_parts)
        
        return headers
    
    async def _ensure_session(self):
        """确保HTTP会话已创建"""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True
            )
    
    async def _get(self, url: str, headers: Dict[str, str] = None) -> Optional[Dict]:
        """发送GET请求"""
        if not HTTPX_AVAILABLE:
            logging.error("httpx 未安装，无法执行HTTP请求")
            return None
        
        await self._ensure_session()
        
        try:
            response = await self._session.get(
                url,
                headers=headers or self.default_headers
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                return data.get('data')
            else:
                logging.warning(f"API 返回非零状态码: {data.get('code')}, {data.get('message', '未知错误')}")
                return None
                
        except httpx.TimeoutException:
            logging.error(f"请求超时: {url}")
            return None
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP错误: {e.response.status_code} - {url}")
            return None
        except Exception as e:
            logging.error(f"请求异常: {e}")
            return None
    
    async def get_room_init(self, room_id: int) -> Optional[Dict]:
        """获取房间初始化信息"""
        url = self.api_room_init.format(room_id=room_id)
        headers = self._get_headers(room_id)
        return await self._get(url, headers)
    
    async def get_room_info(self, room_id: int) -> Optional[Dict]:
        """获取房间信息"""
        url = self.api_room_info.format(room_id=room_id)
        headers = self._get_headers(room_id)
        return await self._get(url, headers)
    
    async def get_play_url(self, room_id: int, quality: int = 10000) -> Optional[Dict]:
        """获取直播流播放地址"""
        url = self.api_play_url.format(room_id=room_id, qn=quality)
        headers = self._get_headers(room_id)
        return await self._get(url, headers)
    
    async def get_live_stream_info(self, room_id: int, preferred_quality: str = "原画") -> Optional[LiveStreamInfo]:
        """
        获取完整的直播流信息
        
        Args:
            room_id: 直播间ID
            preferred_quality: 首选画质
            
        Returns:
            LiveStreamInfo 对象或 None
        """
        room_info = await self.get_room_info(room_id)
        if not room_info:
            room_init = await self.get_room_init(room_id)
            if room_init:
                room_info = {
                    'room_id': room_init.get('room_id', room_id),
                    'title': room_init.get('title', '未知标题'),
                    'live_status': room_init.get('live_status', 0),
                    'online': room_init.get('online', 0)
                }
            else:
                logging.error(f"无法获取房间 {room_id} 的信息")
                return None
        
        live_status = room_info.get('live_status', 0)
        is_live = live_status == 1
        
        if not is_live:
            return LiveStreamInfo(
                room_id=room_id,
                is_live=False,
                title=room_info.get('title', '未知标题'),
                liver_name=room_info.get('anchor_name', ''),
                area_name=room_info.get('area_name', ''),
                cover_url=room_info.get('user_cover', '')
            )
        
        qn = self.quality_qn_map.get(preferred_quality, 10000)
        
        play_data = await self.get_play_url(room_id, qn)
        if not play_data:
            logging.warning(f"无法获取房间 {room_id} 的直播流地址")
            return LiveStreamInfo(
                room_id=room_id,
                is_live=True,
                title=room_info.get('title', '未知标题'),
                liver_name=room_info.get('anchor_name', ''),
                area_name=room_info.get('area_name', ''),
                cover_url=room_info.get('user_cover', '')
            )
        
        stream_urls = self._parse_play_urls(play_data)
        
        return LiveStreamInfo(
            room_id=room_id,
            is_live=True,
            title=room_info.get('title', '未知标题'),
            stream_urls=stream_urls,
            liver_name=room_info.get('anchor_name', ''),
            area_name=room_info.get('area_name', ''),
            cover_url=room_info.get('user_cover', '')
        )
    
    def _parse_play_urls(self, play_data: Dict) -> List[StreamUrl]:
        """解析播放地址数据"""
        stream_urls = []
        
        current_qn = play_data.get('current_qn', 0)
        current_quality = self._qn_to_quality(current_qn)
        
        durl = play_data.get('durl', [])
        for i, item in enumerate(durl):
            url = item.get('url', '')
            if url:
                stream_urls.append(StreamUrl(
                    url=url,
                    quality=current_quality,
                    format=item.get('format', 'flv'),
                    priority=len(durl) - i
                ))
        
        return stream_urls
    
    def _qn_to_quality(self, qn: int) -> str:
        """将qn值转换为画质描述"""
        qn_map = {
            20000: "4K",
            10000: "原画",
            1080: "1080P",
            720: "720P",
            480: "480P",
            360: "360P"
        }
        return qn_map.get(qn, "自动")
    
    async def close(self):
        """关闭HTTP会话"""
        if self._session:
            await self._session.aclose()
            self._session = None


_live_stream_api_instance: Optional[BilibiliLiveStreamAPI] = None


def get_live_stream_api(headers: Dict = None, credential: Dict = None) -> BilibiliLiveStreamAPI:
    """获取全局直播流API实例"""
    global _live_stream_api_instance
    if _live_stream_api_instance is None:
        _live_stream_api_instance = BilibiliLiveStreamAPI(headers=headers, credential=credential)
    return _live_stream_api_instance


async def get_stream_url(room_id: int, credential: Dict = None) -> Optional[str]:
    """
    便捷函数：获取直播流URL
    
    Args:
        room_id: 直播间ID
        credential: 登录凭证（可选）
        
    Returns:
        直播流URL 或 None
    """
    api = BilibiliLiveStreamAPI(credential=credential)
    
    try:
        stream_info = await api.get_live_stream_info(room_id)
        
        if not stream_info or not stream_info.is_live:
            logging.warning(f"房间 {room_id} 未开播或无法获取信息")
            return None
        
        best_url = stream_info.get_best_quality_url()
        if best_url:
            logging.info(f"获取到直播流地址: {best_url.quality}")
            return best_url.url
        else:
            logging.error(f"无法获取房间 {room_id} 的有效直播流地址")
            return None
            
    finally:
        await api.close()
