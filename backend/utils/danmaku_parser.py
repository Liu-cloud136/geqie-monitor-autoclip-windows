"""
弹幕文件解析器
支持多种弹幕格式：
- B站 XML 格式
- JSON 格式
- ASS 格式（部分支持）
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Danmaku:
    """弹幕数据类"""
    id: str = ""
    content: str = ""
    timestamp: float = 0.0
    mode: int = 1
    font_size: int = 25
    color: int = 16777215
    send_time: int = 0
    sender_hash: str = ""
    danmaku_id: str = ""
    pool: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def hex_color(self) -> str:
        return f"#{self.color:06x}"
    
    @property
    def is_scroll(self) -> bool:
        return self.mode in [1, 2, 3, 6]
    
    @property
    def is_top(self) -> bool:
        return self.mode == 5
    
    @property
    def is_bottom(self) -> bool:
        return self.mode == 4


class DanmakuParser:
    """弹幕文件解析器"""
    
    @staticmethod
    def parse(file_path: str) -> Tuple[List[Danmaku], Dict[str, Any]]:
        """
        解析弹幕文件，自动检测格式
        
        Args:
            file_path: 弹幕文件路径
            
        Returns:
            (弹幕列表, 元数据字典)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"弹幕文件不存在: {file_path}")
        
        file_ext = path.suffix.lower()
        
        if file_ext == '.xml':
            return DanmakuParser.parse_bilibili_xml(file_path)
        elif file_ext == '.json':
            return DanmakuParser.parse_json(file_path)
        elif file_ext == '.ass':
            return DanmakuParser.parse_ass(file_path)
        else:
            content = path.read_text(encoding='utf-8', errors='ignore')
            if content.strip().startswith('<?xml') or content.strip().startswith('<i'):
                return DanmakuParser.parse_bilibili_xml(file_path)
            elif content.strip().startswith('[') or content.strip().startswith('{'):
                return DanmakuParser.parse_json(file_path)
            else:
                raise ValueError(f"不支持的弹幕格式: {file_ext}")
    
    @staticmethod
    def parse_bilibili_xml(file_path: str) -> Tuple[List[Danmaku], Dict[str, Any]]:
        """
        解析 B站 XML 格式弹幕
        
        B站弹幕格式参考：
        <d p="时间,模式,字体大小,颜色,发送时间,弹幕池,发送者哈希,弹幕ID">内容</d>
        
        Args:
            file_path: XML 文件路径
            
        Returns:
            (弹幕列表, 元数据字典)
        """
        path = Path(file_path)
        content = path.read_text(encoding='utf-8', errors='ignore')
        
        metadata = {
            'source': 'bilibili',
            'file_name': path.name,
            'parse_time': datetime.now().isoformat()
        }
        
        danmaku_list: List[Danmaku] = []
        
        try:
            root = ET.fromstring(content)
            
            for chatserver in root.findall('.//chatserver'):
                metadata['chatserver'] = chatserver.text
            
            for chatid in root.findall('.//chatid'):
                metadata['chatid'] = chatid.text
            
            for maxlimit in root.findall('.//maxlimit'):
                try:
                    metadata['maxlimit'] = int(maxlimit.text)
                except (ValueError, TypeError):
                    pass
            
            for d_elem in root.findall('.//d'):
                p_attr = d_elem.get('p', '')
                content = d_elem.text or ''
                
                if not p_attr:
                    continue
                
                try:
                    danmaku = DanmakuParser._parse_bilibili_p_attr(p_attr)
                    danmaku.content = content.strip()
                    danmaku_list.append(danmaku)
                except Exception as e:
                    logger.warning(f"解析弹幕失败: {e}, p={p_attr}")
                    continue
        
        except ET.ParseError as e:
            logger.warning(f"XML 解析错误，尝试使用正则解析: {e}")
            danmaku_list = DanmakuParser._parse_bilibili_xml_regex(content)
        
        danmaku_list.sort(key=lambda x: x.timestamp)
        
        metadata['total_count'] = len(danmaku_list)
        if danmaku_list:
            metadata['start_time'] = danmaku_list[0].timestamp
            metadata['end_time'] = danmaku_list[-1].timestamp
        
        logger.info(f"解析完成: 共 {len(danmaku_list)} 条弹幕")
        
        return danmaku_list, metadata
    
    @staticmethod
    def _parse_bilibili_p_attr(p_attr: str) -> Danmaku:
        """
        解析 B站弹幕的 p 属性
        
        p 属性格式：时间,模式,字体大小,颜色,发送时间,弹幕池,发送者哈希,弹幕ID
        """
        parts = p_attr.split(',')
        
        danmaku = Danmaku()
        
        if len(parts) >= 1:
            danmaku.timestamp = float(parts[0])
        
        if len(parts) >= 2:
            danmaku.mode = int(parts[1])
        
        if len(parts) >= 3:
            danmaku.font_size = int(parts[2])
        
        if len(parts) >= 4:
            danmaku.color = int(parts[3])
        
        if len(parts) >= 5:
            danmaku.send_time = int(parts[5]) if parts[5].isdigit() else 0
        
        if len(parts) >= 6:
            danmaku.pool = int(parts[6]) if parts[6].isdigit() else 0
        
        if len(parts) >= 7:
            danmaku.sender_hash = parts[7]
        
        if len(parts) >= 8:
            danmaku.danmaku_id = parts[8]
            danmaku.id = parts[8]
        
        return danmaku
    
    @staticmethod
    def _parse_bilibili_xml_regex(content: str) -> List[Danmaku]:
        """使用正则解析 B站 XML（当 XML 解析失败时的后备方案）"""
        danmaku_list: List[Danmaku] = []
        
        pattern = r'<d\s+p="([^"]+)"[^>]*>([^<]*)</d>'
        matches = re.findall(pattern, content)
        
        for p_attr, text in matches:
            try:
                danmaku = DanmakuParser._parse_bilibili_p_attr(p_attr)
                danmaku.content = text.strip()
                danmaku_list.append(danmaku)
            except Exception as e:
                logger.warning(f"正则解析弹幕失败: {e}")
                continue
        
        return danmaku_list
    
    @staticmethod
    def parse_json(file_path: str) -> Tuple[List[Danmaku], Dict[str, Any]]:
        """
        解析 JSON 格式弹幕
        
        支持的 JSON 格式：
        - 数组格式: [{content, timestamp, ...}, ...]
        - 对象格式: {danmaku: [...], metadata: {...}}
        """
        path = Path(file_path)
        content = path.read_text(encoding='utf-8', errors='ignore')
        data = json.loads(content)
        
        metadata = {
            'source': 'json',
            'file_name': path.name,
            'parse_time': datetime.now().isoformat()
        }
        
        danmaku_list: List[Danmaku] = []
        
        if isinstance(data, list):
            for item in data:
                danmaku = DanmakuParser._json_item_to_danmaku(item)
                if danmaku:
                    danmaku_list.append(danmaku)
        elif isinstance(data, dict):
            if 'metadata' in data:
                metadata.update(data['metadata'])
            
            danmaku_data = data.get('danmaku', data.get('items', data.get('list', [])))
            for item in danmaku_data:
                danmaku = DanmakuParser._json_item_to_danmaku(item)
                if danmaku:
                    danmaku_list.append(danmaku)
        
        danmaku_list.sort(key=lambda x: x.timestamp)
        
        metadata['total_count'] = len(danmaku_list)
        if danmaku_list:
            metadata['start_time'] = danmaku_list[0].timestamp
            metadata['end_time'] = danmaku_list[-1].timestamp
        
        return danmaku_list, metadata
    
    @staticmethod
    def _json_item_to_danmaku(item: Dict[str, Any]) -> Optional[Danmaku]:
        """将 JSON 对象转换为 Danmaku"""
        if not isinstance(item, dict):
            return None
        
        content = item.get('content', item.get('text', item.get('msg', '')))
        if not content:
            return None
        
        danmaku = Danmaku()
        danmaku.content = str(content).strip()
        
        if 'id' in item:
            danmaku.id = str(item['id'])
        
        if 'timestamp' in item:
            danmaku.timestamp = float(item['timestamp'])
        elif 'time' in item:
            danmaku.timestamp = float(item['time'])
        elif 'progress' in item:
            danmaku.timestamp = float(item['progress'])
        
        if 'mode' in item:
            danmaku.mode = int(item['mode'])
        elif 'type' in item:
            danmaku.mode = int(item['type'])
        
        if 'font_size' in item:
            danmaku.font_size = int(item['font_size'])
        elif 'size' in item:
            danmaku.font_size = int(item['size'])
        
        if 'color' in item:
            color_val = item['color']
            if isinstance(color_val, str) and color_val.startswith('#'):
                try:
                    danmaku.color = int(color_val[1:], 16)
                except ValueError:
                    pass
            else:
                danmaku.color = int(color_val)
        
        if 'send_time' in item:
            danmaku.send_time = int(item['send_time'])
        
        if 'sender_hash' in item:
            danmaku.sender_hash = str(item['sender_hash'])
        elif 'sender' in item:
            danmaku.sender_hash = str(item['sender'])
        
        if 'danmaku_id' in item:
            danmaku.danmaku_id = str(item['danmaku_id'])
        
        if 'pool' in item:
            danmaku.pool = int(item['pool'])
        
        return danmaku
    
    @staticmethod
    def parse_ass(file_path: str) -> Tuple[List[Danmaku], Dict[str, Any]]:
        """
        解析 ASS 格式弹幕（部分支持）
        
        主要解析弹幕事件行
        """
        path = Path(file_path)
        content = path.read_text(encoding='utf-8', errors='ignore')
        
        metadata = {
            'source': 'ass',
            'file_name': path.name,
            'parse_time': datetime.now().isoformat()
        }
        
        danmaku_list: List[Danmaku] = []
        
        for line in content.split('\n'):
            if line.startswith('Dialogue:'):
                try:
                    danmaku = DanmakuParser._parse_ass_dialogue(line)
                    if danmaku and danmaku.content:
                        danmaku_list.append(danmaku)
                except Exception as e:
                    logger.warning(f"解析 ASS 弹幕失败: {e}")
                    continue
        
        danmaku_list.sort(key=lambda x: x.timestamp)
        
        metadata['total_count'] = len(danmaku_list)
        if danmaku_list:
            metadata['start_time'] = danmaku_list[0].timestamp
            metadata['end_time'] = danmaku_list[-1].timestamp
        
        return danmaku_list, metadata
    
    @staticmethod
    def _parse_ass_dialogue(line: str) -> Optional[Danmaku]:
        """解析 ASS Dialogue 行"""
        line = line[len('Dialogue:'):].strip()
        
        parts = line.split(',', 9)
        if len(parts) < 10:
            return None
        
        start_time_str = parts[1].strip()
        content = parts[9].strip() if len(parts) > 9 else ''
        
        if not content or content.startswith('{\\an'):
            return None
        
        if '\\an' in content:
            content = re.sub(r'\{\\an\d+\}', '', content)
        
        danmaku = Danmaku()
        danmaku.content = content
        danmaku.timestamp = DanmakuParser._ass_time_to_seconds(start_time_str)
        
        if '\\an8' in line:
            danmaku.mode = 5
        elif '\\an2' in line or '\\an3' in line:
            danmaku.mode = 4
        else:
            danmaku.mode = 1
        
        color_match = re.search(r'\\c&H([0-9A-Fa-f]+)&', line)
        if color_match:
            try:
                hex_color = color_match.group(1)
                if len(hex_color) == 6:
                    bgr = int(hex_color, 16)
                    r = (bgr >> 16) & 0xFF
                    g = (bgr >> 8) & 0xFF
                    b = bgr & 0xFF
                    danmaku.color = (r << 16) | (g << 8) | b
            except ValueError:
                pass
        
        return danmaku
    
    @staticmethod
    def _ass_time_to_seconds(time_str: str) -> float:
        """将 ASS 时间格式 (H:MM:SS.cc) 转换为秒"""
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds_parts = parts[2].split('.')
                seconds = int(seconds_parts[0])
                centiseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
                return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
            elif len(parts) == 2:
                minutes = int(parts[0])
                seconds_parts = parts[1].split('.')
                seconds = int(seconds_parts[0])
                centiseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
                return minutes * 60 + seconds + centiseconds / 100.0
        except (ValueError, IndexError):
            pass
        
        return 0.0


def save_danmaku_to_json(danmaku_list: List[Danmaku], output_path: str, metadata: Dict[str, Any] = None):
    """将弹幕列表保存为 JSON 文件"""
    data = {
        'metadata': metadata or {},
        'danmaku': [d.to_dict() for d in danmaku_list]
    }
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"弹幕已保存到: {output_path}")
