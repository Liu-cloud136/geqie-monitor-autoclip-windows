"""
弹幕分析器
提供弹幕热度分析、关键词提取、情感分析等功能
用于计算弹幕评分维度，辅助切片挑选
"""

import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime

from utils.danmaku_parser import Danmaku

logger = logging.getLogger(__name__)


@dataclass
class DanmakuHeatPoint:
    """弹幕热度点"""
    start_time: float = 0.0
    end_time: float = 0.0
    center_time: float = 0.0
    danmaku_count: int = 0
    density: float = 0.0
    keywords: List[str] = field(default_factory=list)
    sentiment_score: float = 0.5
    heat_score: float = 0.0


@dataclass
class DanmakuSegmentAnalysis:
    """视频片段弹幕分析结果"""
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    
    danmaku_count: int = 0
    danmaku_density: float = 0.0
    
    scroll_danmaku_count: int = 0
    top_danmaku_count: int = 0
    bottom_danmaku_count: int = 0
    
    keywords: List[Tuple[str, int]] = field(default_factory=list)
    special_danmaku: List[Dict[str, Any]] = field(default_factory=list)
    
    sentiment_positive: float = 0.0
    sentiment_negative: float = 0.0
    sentiment_neutral: float = 0.0
    overall_sentiment: float = 0.5
    
    heat_score: float = 0.0
    keyword_score: float = 0.0
    sentiment_score: float = 0.0
    special_score: float = 0.0
    
    total_danmaku_score: float = 0.0


@dataclass
class DanmakuAnalysisResult:
    """弹幕分析完整结果"""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    total_danmaku_count: int = 0
    video_duration: float = 0.0
    
    heat_points: List[DanmakuHeatPoint] = field(default_factory=list)
    
    overall_keywords: List[Tuple[str, int]] = field(default_factory=list)
    
    segment_analyses: List[DanmakuSegmentAnalysis] = field(default_factory=list)
    
    special_danmaku_summary: List[Dict[str, Any]] = field(default_factory=list)
    
    overall_sentiment: Dict[str, float] = field(default_factory=lambda: {
        'positive': 0.0,
        'negative': 0.0,
        'neutral': 0.0
    })


SPECIAL_DANMAKU_PATTERNS = {
    'high_energy': [
        r'前方高能', r'高能预警', r'前方核能', r'核能预警',
        r'名场面', r'经典场面', r'封神时刻', r'神级',
        r'前方爆笑', r'笑点密集', r'笑死人',
        r'泪目', r'哭了', r'感动', r'破防',
        r'卧槽', r'我靠', r'牛[逼批]', r'太强了', r'厉害',
        r'awsl', r'阿伟死了',
        r'反复观看', r'看了[^\s]*遍', r'再来[^\s]*遍',
        r'收藏', r'保存', r'录屏'
    ],
    'warning': [
        r'前方注意', r'注意前方', r'预警',
        r'胆小慎入', r'高血压慎入', r'心脏病慎入',
        r'调低音量', r'戴好耳机', r'注意音量'
    ],
    'timing': [
        r'空降成功', r'空降坐标', r'直接跳到',
        r'快进', r'跳过', r'倍速'
    ],
    'negative': [
        r'没意思', r'无聊', r'不好看', r'垃圾',
        r'失望', r'就这', r'这就完了',
        r'尴尬', r'尴尬癌', r'脚趾抠地'
    ],
    'question': [
        r'为什么', r'怎么回事', r'谁来解释', r'不懂',
        r'啥意思', r'什么梗', r'求科普'
    ]
}

POSITIVE_KEYWORDS = [
    '好看', '精彩', '厉害', '牛', '强', '棒', '优秀',
    '喜欢', '爱', '支持', '加油', '太棒了', '太好了',
    '感动', '泪目', '暖心', '治愈', '有趣', '搞笑',
    '爆笑', '哈哈', '233', 'awsl', '神', '经典', '名场面'
]

NEGATIVE_KEYWORDS = [
    '无聊', '没意思', '垃圾', '失望', '尴尬', '难看',
    '不好看', '就这', '水', '划水', '没意思', '无聊',
    '浪费时间', '看不下去', '弃了', '劝退', '尴尬癌'
]


class DanmakuAnalyzer:
    """弹幕分析器"""
    
    def __init__(self, window_seconds: float = 10.0, slide_seconds: float = 5.0):
        """
        初始化弹幕分析器
        
        Args:
            window_seconds: 滑动窗口大小（秒）
            slide_seconds: 滑动步长（秒）
        """
        self.window_seconds = window_seconds
        self.slide_seconds = slide_seconds
        
        self.special_patterns: Dict[str, List[re.Pattern]] = {}
        for category, patterns in SPECIAL_DANMAKU_PATTERNS.items():
            self.special_patterns[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def analyze(self, danmaku_list: List[Danmaku], 
                video_duration: Optional[float] = None) -> DanmakuAnalysisResult:
        """
        分析弹幕列表
        
        Args:
            danmaku_list: 弹幕列表
            video_duration: 视频时长（秒），如果为 None 则从弹幕时间推断
            
        Returns:
            DanmakuAnalysisResult: 完整分析结果
        """
        if not danmaku_list:
            logger.warning("弹幕列表为空，无法分析")
            return DanmakuAnalysisResult()
        
        danmaku_list = sorted(danmaku_list, key=lambda x: x.timestamp)
        
        if video_duration is None:
            video_duration = danmaku_list[-1].timestamp + 10.0
        
        result = DanmakuAnalysisResult()
        result.total_danmaku_count = len(danmaku_list)
        result.video_duration = video_duration
        
        result.heat_points = self._find_heat_points(danmaku_list, video_duration)
        
        result.overall_keywords = self._extract_overall_keywords(danmaku_list)
        
        result.segment_analyses = self._analyze_segments(
            danmaku_list, video_duration
        )
        
        result.special_danmaku_summary = self._find_special_danmaku(danmaku_list)
        
        result.overall_sentiment = self._analyze_overall_sentiment(danmaku_list)
        
        result.metadata = {
            'window_seconds': self.window_seconds,
            'slide_seconds': self.slide_seconds,
            'analysis_time': datetime.now().isoformat()
        }
        
        return result
    
    def _find_heat_points(self, danmaku_list: List[Danmaku], 
                          video_duration: float) -> List[DanmakuHeatPoint]:
        """
        查找弹幕热度点
        
        使用滑动窗口计算弹幕密度，找出高热度时间段
        """
        if not danmaku_list:
            return []
        
        heat_points: List[DanmakuHeatPoint] = []
        
        timestamps = [d.timestamp for d in danmaku_list]
        min_time = min(timestamps)
        max_time = max(timestamps)
        
        window_size = self.window_seconds
        slide_step = self.slide_seconds
        
        current_time = max(0, min_time - window_size / 2)
        end_time = max_time + window_size
        
        all_windows: List[Dict[str, Any]] = []
        
        while current_time < end_time:
            window_start = current_time
            window_end = current_time + window_size
            
            window_danmaku = [
                d for d in danmaku_list 
                if window_start <= d.timestamp < window_end
            ]
            
            if window_danmaku:
                density = len(window_danmaku) / window_size
                
                center_time = (window_start + window_end) / 2
                
                window_keywords = self._extract_keywords_from_danmaku(window_danmaku, top_n=5)
                
                sentiment = self._analyze_segment_sentiment(window_danmaku)
                
                heat_score = self._calculate_heat_score(
                    len(window_danmaku), density, window_keywords, sentiment
                )
                
                all_windows.append({
                    'start_time': window_start,
                    'end_time': window_end,
                    'center_time': center_time,
                    'danmaku_count': len(window_danmaku),
                    'density': density,
                    'keywords': [k for k, _ in window_keywords],
                    'sentiment_score': sentiment,
                    'heat_score': heat_score
                })
            
            current_time += slide_step
        
        if not all_windows:
            return []
        
        all_windows.sort(key=lambda x: x['heat_score'], reverse=True)
        
        merged_windows = self._merge_overlapping_windows(all_windows)
        
        for window in merged_windows:
            heat_point = DanmakuHeatPoint(
                start_time=window['start_time'],
                end_time=window['end_time'],
                center_time=window['center_time'],
                danmaku_count=window['danmaku_count'],
                density=window['density'],
                keywords=window.get('keywords', []),
                sentiment_score=window.get('sentiment_score', 0.5),
                heat_score=window['heat_score']
            )
            heat_points.append(heat_point)
        
        heat_points.sort(key=lambda x: x.heat_score, reverse=True)
        
        return heat_points[:50]
    
    def _merge_overlapping_windows(self, windows: List[Dict]) -> List[Dict]:
        """合并重叠的高热度窗口"""
        if not windows:
            return []
        
        sorted_windows = sorted(windows, key=lambda x: x['start_time'])
        
        merged: List[Dict] = []
        current = sorted_windows[0]
        
        for window in sorted_windows[1:]:
            if window['start_time'] <= current['end_time']:
                current['end_time'] = max(current['end_time'], window['end_time'])
                current['center_time'] = (current['start_time'] + current['end_time']) / 2
                current['danmaku_count'] = max(current['danmaku_count'], window['danmaku_count'])
                current['density'] = max(current['density'], window['density'])
                current['heat_score'] = max(current['heat_score'], window['heat_score'])
                
                current_keywords = set(current.get('keywords', []))
                current_keywords.update(window.get('keywords', []))
                current['keywords'] = list(current_keywords)[:10]
            else:
                merged.append(current)
                current = window
        
        merged.append(current)
        
        return sorted(merged, key=lambda x: x['heat_score'], reverse=True)
    
    def _calculate_heat_score(self, count: int, density: float, 
                               keywords: List[Tuple[str, int]], 
                               sentiment: float) -> float:
        """计算热度分数"""
        count_score = min(count / 20.0, 1.0) * 40
        
        density_score = min(density / 3.0, 1.0) * 30
        
        keyword_score = min(len(keywords) / 5.0, 1.0) * 20
        
        sentiment_score = abs(sentiment - 0.5) * 2 * 10
        
        total = count_score + density_score + keyword_score + sentiment_score
        
        return total
    
    def _extract_overall_keywords(self, danmaku_list: List[Danmaku]) -> List[Tuple[str, int]]:
        """提取整体关键词"""
        return self._extract_keywords_from_danmaku(danmaku_list, top_n=50)
    
    def _extract_keywords_from_danmaku(self, danmaku_list: List[Danmaku], 
                                        top_n: int = 20) -> List[Tuple[str, int]]:
        """从弹幕列表中提取关键词"""
        word_counter: Counter = Counter()
        
        for danmaku in danmaku_list:
            words = self._segment_text(danmaku.content)
            word_counter.update(words)
        
        filtered_words = [
            (word, count) for word, count in word_counter.most_common(top_n * 2)
            if len(word) >= 2 and not self._is_stop_word(word)
        ]
        
        return filtered_words[:top_n]
    
    def _segment_text(self, text: str) -> List[str]:
        """简单的文本分词（基于正则表达式）"""
        text = text.lower()
        
        english_words = re.findall(r'[a-zA-Z]{2,}', text)
        
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]+', text)
        chinese_words: List[str] = []
        for chars in chinese_chars:
            if len(chars) == 2:
                chinese_words.append(chars)
            elif len(chars) > 2:
                for i in range(len(chars) - 1):
                    chinese_words.append(chars[i:i+2])
        
        numbers = re.findall(r'\d{3,}', text)
        
        all_words = english_words + chinese_words + numbers
        
        return all_words
    
    def _is_stop_word(self, word: str) -> bool:
        """判断是否为停用词"""
        stop_words = {
            '的', '了', '是', '在', '有', '和', '就', '不', '人', '都',
            '一', '一个', '这个', '那个', '什么', '怎么', '为什么',
            '我', '你', '他', '她', '它', '们',
            '这', '那', '哪', '谁', '什么', '怎么', '为什么',
            '啊', '吧', '呢', '吗', '呀', '哦', '哈', '哇'
        }
        return word in stop_words or len(word) < 2
    
    def _analyze_segments(self, danmaku_list: List[Danmaku], 
                          video_duration: float) -> List[DanmakuSegmentAnalysis]:
        """分析视频片段（用于与现有切片时间线对齐）"""
        segments: List[DanmakuSegmentAnalysis] = []
        
        if not danmaku_list:
            return segments
        
        segment_duration = 60.0
        num_segments = int(video_duration / segment_duration) + 1
        
        for i in range(num_segments):
            start_time = i * segment_duration
            end_time = (i + 1) * segment_duration
            
            segment_danmaku = [
                d for d in danmaku_list
                if start_time <= d.timestamp < end_time
            ]
            
            if segment_danmaku:
                analysis = self._analyze_single_segment(
                    segment_danmaku, start_time, end_time
                )
                segments.append(analysis)
        
        return segments
    
    def _analyze_single_segment(self, danmaku_list: List[Danmaku],
                                start_time: float, end_time: float) -> DanmakuSegmentAnalysis:
        """分析单个片段"""
        analysis = DanmakuSegmentAnalysis()
        analysis.start_time = start_time
        analysis.end_time = end_time
        analysis.duration = end_time - start_time
        
        analysis.danmaku_count = len(danmaku_list)
        analysis.danmaku_density = analysis.danmaku_count / analysis.duration if analysis.duration > 0 else 0
        
        for d in danmaku_list:
            if d.is_scroll:
                analysis.scroll_danmaku_count += 1
            elif d.is_top:
                analysis.top_danmaku_count += 1
            elif d.is_bottom:
                analysis.bottom_danmaku_count += 1
        
        analysis.keywords = self._extract_keywords_from_danmaku(danmaku_list, top_n=10)
        
        sentiment = self._analyze_segment_sentiment(danmaku_list)
        analysis.overall_sentiment = sentiment
        
        positive_count = sum(1 for d in danmaku_list if self._is_positive_danmaku(d.content))
        negative_count = sum(1 for d in danmaku_list if self._is_negative_danmaku(d.content))
        total = len(danmaku_list)
        
        if total > 0:
            analysis.sentiment_positive = positive_count / total
            analysis.sentiment_negative = negative_count / total
            analysis.sentiment_neutral = (total - positive_count - negative_count) / total
        
        special_danmaku = self._find_special_danmaku_in_segment(danmaku_list)
        analysis.special_danmaku = special_danmaku
        
        analysis.heat_score = min(analysis.danmaku_density / 2.0, 1.0) * 100
        analysis.keyword_score = min(len(analysis.keywords) / 5.0, 1.0) * 100
        analysis.sentiment_score = abs(analysis.overall_sentiment - 0.5) * 2 * 100
        analysis.special_score = min(len(analysis.special_danmaku) / 3.0, 1.0) * 100
        
        analysis.total_danmaku_score = (
            analysis.heat_score * 0.4 +
            analysis.keyword_score * 0.2 +
            analysis.sentiment_score * 0.2 +
            analysis.special_score * 0.2
        )
        
        return analysis
    
    def _analyze_segment_sentiment(self, danmaku_list: List[Danmaku]) -> float:
        """分析片段情感倾向（0-1，0.5为中性，<0.5负面，>0.5正面）"""
        if not danmaku_list:
            return 0.5
        
        positive_score = 0.0
        negative_score = 0.0
        total = 0.0
        
        for d in danmaku_list:
            content = d.content.lower()
            
            pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in content)
            neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in content)
            
            if pos_count > neg_count:
                positive_score += 1.0
                total += 1.0
            elif neg_count > pos_count:
                negative_score += 1.0
                total += 1.0
            else:
                total += 0.5
        
        if total == 0:
            return 0.5
        
        return (positive_score + total * 0.25) / (positive_score + negative_score + total * 0.5)
    
    def _is_positive_danmaku(self, content: str) -> bool:
        """判断弹幕是否为正面"""
        content = content.lower()
        return any(kw in content for kw in POSITIVE_KEYWORDS)
    
    def _is_negative_danmaku(self, content: str) -> bool:
        """判断弹幕是否为负面"""
        content = content.lower()
        return any(kw in content for kw in NEGATIVE_KEYWORDS)
    
    def _find_special_danmaku(self, danmaku_list: List[Danmaku]) -> List[Dict[str, Any]]:
        """查找特殊弹幕"""
        special_list: List[Dict[str, Any]] = []
        
        for d in danmaku_list:
            for category, patterns in self.special_patterns.items():
                for pattern in patterns:
                    if pattern.search(d.content):
                        special_list.append({
                            'timestamp': d.timestamp,
                            'content': d.content,
                            'category': category,
                            'danmaku_id': d.id
                        })
                        break
        
        special_list.sort(key=lambda x: x['timestamp'])
        
        return special_list
    
    def _find_special_danmaku_in_segment(self, danmaku_list: List[Danmaku]) -> List[Dict[str, Any]]:
        """在片段中查找特殊弹幕"""
        return self._find_special_danmaku(danmaku_list)[:20]
    
    def _analyze_overall_sentiment(self, danmaku_list: List[Danmaku]) -> Dict[str, float]:
        """分析整体情感倾向"""
        if not danmaku_list:
            return {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34}
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for d in danmaku_list:
            is_pos = self._is_positive_danmaku(d.content)
            is_neg = self._is_negative_danmaku(d.content)
            
            if is_pos and not is_neg:
                positive_count += 1
            elif is_neg and not is_pos:
                negative_count += 1
            else:
                neutral_count += 1
        
        total = len(danmaku_list)
        
        return {
            'positive': positive_count / total,
            'negative': negative_count / total,
            'neutral': neutral_count / total
        }
    
    def get_score_for_time_range(self, start_time: float, end_time: float,
                                 analysis_result: DanmakuAnalysisResult) -> Dict[str, float]:
        """
        获取指定时间范围的弹幕评分
        
        Args:
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            analysis_result: 弹幕分析结果
            
        Returns:
            包含各维度评分的字典
        """
        heat_score = 0.0
        keyword_score = 0.0
        sentiment_score = 0.0
        special_score = 0.0
        
        for hp in analysis_result.heat_points:
            overlap = self._calculate_time_overlap(
                start_time, end_time, hp.start_time, hp.end_time
            )
            if overlap > 0:
                heat_score = max(heat_score, hp.heat_score * (overlap / (end_time - start_time)))
        
        for sa in analysis_result.segment_analyses:
            overlap = self._calculate_time_overlap(
                start_time, end_time, sa.start_time, sa.end_time
            )
            if overlap > 0:
                keyword_score = max(keyword_score, sa.keyword_score)
                sentiment_score = max(sentiment_score, sa.sentiment_score)
                special_score = max(special_score, sa.special_score)
        
        for sd in analysis_result.special_danmaku_summary:
            if start_time <= sd['timestamp'] < end_time:
                category = sd.get('category', '')
                if category == 'high_energy':
                    special_score = max(special_score, 100.0)
                elif category == 'warning':
                    special_score = max(special_score, 75.0)
        
        total_score = (
            heat_score * 0.4 +
            keyword_score * 0.2 +
            sentiment_score * 0.2 +
            special_score * 0.2
        )
        
        return {
            'heat_score': round(heat_score, 2),
            'keyword_score': round(keyword_score, 2),
            'sentiment_score': round(sentiment_score, 2),
            'special_score': round(special_score, 2),
            'total_danmaku_score': round(total_score, 2)
        }
    
    def _calculate_time_overlap(self, s1: float, e1: float, s2: float, e2: float) -> float:
        """计算两个时间区间的重叠时长"""
        overlap_start = max(s1, s2)
        overlap_end = min(e1, e2)
        
        if overlap_start >= overlap_end:
            return 0.0
        
        return overlap_end - overlap_start


def save_analysis_result(result: DanmakuAnalysisResult, output_path: str):
    """保存分析结果到 JSON 文件"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        'metadata': result.metadata,
        'total_danmaku_count': result.total_danmaku_count,
        'video_duration': result.video_duration,
        'overall_keywords': [{'word': k, 'count': c} for k, c in result.overall_keywords],
        'overall_sentiment': result.overall_sentiment,
        'heat_points': [asdict(hp) for hp in result.heat_points],
        'special_danmaku_summary': result.special_danmaku_summary,
        'segment_analyses': [asdict(sa) for sa in result.segment_analyses]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"弹幕分析结果已保存到: {output_path}")


def load_analysis_result(input_path: str) -> DanmakuAnalysisResult:
    """从 JSON 文件加载分析结果"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    result = DanmakuAnalysisResult()
    result.metadata = data.get('metadata', {})
    result.total_danmaku_count = data.get('total_danmaku_count', 0)
    result.video_duration = data.get('video_duration', 0.0)
    result.overall_keywords = [
        (item['word'], item['count']) 
        for item in data.get('overall_keywords', [])
    ]
    result.overall_sentiment = data.get('overall_sentiment', {'positive': 0, 'negative': 0, 'neutral': 0})
    
    for hp_data in data.get('heat_points', []):
        hp = DanmakuHeatPoint(**hp_data)
        result.heat_points.append(hp)
    
    result.special_danmaku_summary = data.get('special_danmaku_summary', [])
    
    for sa_data in data.get('segment_analyses', []):
        sa = DanmakuSegmentAnalysis(**sa_data)
        result.segment_analyses.append(sa)
    
    return result
