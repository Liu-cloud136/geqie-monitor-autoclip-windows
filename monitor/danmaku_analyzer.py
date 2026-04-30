#!/usr/bin/env python3
"""
弹幕分析模块 - 对弹幕内容进行情感倾向分析、词云生成、话题提取等
"""

import re
import time
import logging
import hashlib
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    from snownlp import SnowNLP
    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False
    logging.warning("SnowNLP 未安装，情感分析功能将不可用")

try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logging.warning("jieba 未安装，分词功能将不可用")

try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False
    logging.warning("wordcloud 未安装，词云生成功能将不可用")


class SentimentType(Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class DanmakuAnalysis:
    danmaku_id: str
    username: str
    content: str
    timestamp: float
    room_id: int
    
    sentiment_score: float = 0.5
    sentiment_type: SentimentType = SentimentType.NEUTRAL
    
    keywords: List[str] = field(default_factory=list)
    word_count: int = 0
    
    is_duplicate: bool = False
    duplicate_count: int = 0
    duplicate_group_id: Optional[str] = None
    
    is_suspicious: bool = False
    suspicious_reason: Optional[str] = None
    
    user_behavior_score: float = 0.5


@dataclass
class UserProfile:
    username: str
    total_danmaku: int = 0
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    avg_sentiment: float = 0.5
    keywords: Counter = field(default_factory=Counter)
    active_time_slots: Dict[int, int] = field(default_factory=dict)
    duplicate_ratio: float = 0.0
    first_seen: float = 0.0
    last_seen: float = 0.0


@dataclass
class DuplicateGroup:
    content_hash: str
    content_sample: str
    count: int = 0
    users: Counter = field(default_factory=Counter)
    first_seen: float = 0.0
    last_seen: float = 0.0
    avg_sentiment: float = 0.5


@dataclass
class HotTopic:
    keyword: str
    count: int = 0
    trend_score: float = 0.0
    related_danmaku: List[Dict] = field(default_factory=list)


class DanmakuAnalyzer:
    """弹幕分析器 - 实时分析弹幕内容"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, 
                 max_history: int = 10000,
                 sentiment_positive_threshold: float = 0.6,
                 sentiment_negative_threshold: float = 0.4,
                 duplicate_similarity_threshold: float = 0.8,
                 max_duplicate_groups: int = 100,
                 max_users: int = 1000):
        
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        
        self.max_history = max_history
        self.sentiment_positive_threshold = sentiment_positive_threshold
        self.sentiment_negative_threshold = sentiment_negative_threshold
        self.duplicate_similarity_threshold = duplicate_similarity_threshold
        self.max_duplicate_groups = max_duplicate_groups
        self.max_users = max_users
        
        self.danmaku_history: List[DanmakuAnalysis] = []
        self.user_profiles: Dict[str, UserProfile] = {}
        self.duplicate_groups: Dict[str, DuplicateGroup] = {}
        self.content_hash_map: Dict[str, str] = {}
        
        self._lock = threading.RLock()
        
        if JIEBA_AVAILABLE:
            self._init_jieba()
        
        logging.info("弹幕分析器初始化完成")
        logging.info(f"  - SnowNLP: {'可用' if SNOWNLP_AVAILABLE else '不可用'}")
        logging.info(f"  - jieba: {'可用' if JIEBA_AVAILABLE else '不可用'}")
        logging.info(f"  - wordcloud: {'可用' if WORDCLOUD_AVAILABLE else '不可用'}")
    
    def _init_jieba(self):
        """初始化jieba分词"""
        try:
            jieba.initialize()
            logging.info("jieba分词初始化完成")
        except Exception as e:
            logging.warning(f"jieba初始化失败: {e}")
    
    def analyze_sentiment(self, text: str) -> Tuple[float, SentimentType]:
        """
        分析情感倾向
        Returns: (情感分数 0-1, 情感类型)
        """
        if not SNOWNLP_AVAILABLE or not text.strip():
            return 0.5, SentimentType.NEUTRAL
        
        try:
            s = SnowNLP(text)
            score = s.sentiments
            
            if score >= self.sentiment_positive_threshold:
                sentiment_type = SentimentType.POSITIVE
            elif score <= self.sentiment_negative_threshold:
                sentiment_type = SentimentType.NEGATIVE
            else:
                sentiment_type = SentimentType.NEUTRAL
            
            return score, sentiment_type
        except Exception as e:
            logging.debug(f"情感分析出错: {e}")
            return 0.5, SentimentType.NEUTRAL
    
    def extract_keywords(self, text: str, topK: int = 5) -> List[str]:
        """
        提取关键词
        """
        if not JIEBA_AVAILABLE or not text.strip():
            return []
        
        try:
            keywords = jieba.analyse.extract_tags(text, topK=topK)
            return keywords
        except Exception as e:
            logging.debug(f"关键词提取出错: {e}")
            return []
    
    def segment_text(self, text: str) -> List[str]:
        """
        分词
        """
        if not JIEBA_AVAILABLE or not text.strip():
            return list(text)
        
        try:
            return list(jieba.cut(text))
        except Exception as e:
            logging.debug(f"分词出错: {e}")
            return list(text)
    
    def calculate_content_hash(self, text: str) -> str:
        """
        计算内容哈希（用于去重）
        使用标准化后的文本计算MD5哈希
        """
        normalized = self._normalize_text(text)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:16]
    
    def _normalize_text(self, text: str) -> str:
        """
        文本标准化 - 用于去重检测
        """
        text = text.lower()
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)
        return text
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（基于Jaccard距离）
        """
        words1 = set(self.segment_text(text1))
        words2 = set(self.segment_text(text2))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def detect_duplicate(self, text: str, timestamp: float, username: str) -> Tuple[bool, int, Optional[str]]:
        """
        检测重复弹幕
        Returns: (是否重复, 重复次数, 重复组ID)
        """
        content_hash = self.calculate_content_hash(text)
        
        with self._lock:
            if content_hash in self.duplicate_groups:
                group = self.duplicate_groups[content_hash]
                group.count += 1
                group.users[username] += 1
                group.last_seen = timestamp
                
                sentiment_score, _ = self.analyze_sentiment(text)
                group.avg_sentiment = (group.avg_sentiment * (group.count - 1) + sentiment_score) / group.count
                
                return True, group.count, content_hash
            else:
                if len(self.duplicate_groups) >= self.max_duplicate_groups:
                    self._cleanup_duplicate_groups()
                
                sentiment_score, _ = self.analyze_sentiment(text)
                self.duplicate_groups[content_hash] = DuplicateGroup(
                    content_hash=content_hash,
                    content_sample=text[:50],
                    count=1,
                    users=Counter({username: 1}),
                    first_seen=timestamp,
                    last_seen=timestamp,
                    avg_sentiment=sentiment_score
                )
                
                return False, 1, content_hash
    
    def _cleanup_duplicate_groups(self):
        """清理最旧的重复组"""
        if not self.duplicate_groups:
            return
        
        sorted_groups = sorted(
            self.duplicate_groups.items(),
            key=lambda x: x[1].last_seen
        )
        
        remove_count = len(self.duplicate_groups) - self.max_duplicate_groups // 2
        for i in range(remove_count):
            if i < len(sorted_groups):
                del self.duplicate_groups[sorted_groups[i][0]]
    
    def detect_suspicious_behavior(self, 
                                     username: str, 
                                     content: str, 
                                     timestamp: float) -> Tuple[bool, Optional[str]]:
        """
        检测潜在的"带节奏"行为
        规则：
        1. 短时间内发送大量重复内容
        2. 负面情绪倾向的内容在短时间内被大量转发
        3. 特定用户在短时间内发送大量负面弹幕
        """
        with self._lock:
            user_profile = self.user_profiles.get(username)
            
            if user_profile:
                recent_time = timestamp - 60
                recent_negative = sum(
                    1 for d in self.danmaku_history[-100:]
                    if d.username == username 
                    and d.timestamp > recent_time
                    and d.sentiment_type == SentimentType.NEGATIVE
                )
                
                if recent_negative >= 5:
                    return True, "短时间内发送大量负面弹幕"
                
                if user_profile.duplicate_ratio > 0.7 and user_profile.total_danmaku > 10:
                    return True, "重复内容比例过高"
            
            content_hash = self.calculate_content_hash(content)
            if content_hash in self.duplicate_groups:
                group = self.duplicate_groups[content_hash]
                
                if group.count >= 10 and group.avg_sentiment < 0.4:
                    return True, "负面内容被大量重复发送"
                
                time_span = group.last_seen - group.first_seen
                if group.count >= 5 and time_span < 60:
                    return True, "短时间内大量用户发送相同内容"
        
        return False, None
    
    def update_user_profile(self, 
                            username: str, 
                            analysis: DanmakuAnalysis,
                            timestamp: float):
        """
        更新用户画像
        """
        with self._lock:
            if username not in self.user_profiles:
                if len(self.user_profiles) >= self.max_users:
                    self._cleanup_user_profiles()
                
                self.user_profiles[username] = UserProfile(
                    username=username,
                    first_seen=timestamp
                )
            
            profile = self.user_profiles[username]
            profile.total_danmaku += 1
            profile.last_seen = timestamp
            
            if analysis.sentiment_type == SentimentType.POSITIVE:
                profile.positive_count += 1
            elif analysis.sentiment_type == SentimentType.NEGATIVE:
                profile.negative_count += 1
            else:
                profile.neutral_count += 1
            
            total_sentiment = (
                profile.positive_count * 0.8 +
                profile.neutral_count * 0.5 +
                profile.negative_count * 0.2
            )
            profile.avg_sentiment = total_sentiment / profile.total_danmaku if profile.total_danmaku > 0 else 0.5
            
            for keyword in analysis.keywords:
                profile.keywords[keyword] += 1
            
            hour = datetime.fromtimestamp(timestamp).hour
            profile.active_time_slots[hour] = profile.active_time_slots.get(hour, 0) + 1
            
            if analysis.is_duplicate:
                duplicate_total = sum(
                    1 for d in self.danmaku_history[-1000:]
                    if d.username == username and d.is_duplicate
                )
                profile.duplicate_ratio = duplicate_total / profile.total_danmaku if profile.total_danmaku > 0 else 0.0
    
    def _cleanup_user_profiles(self):
        """清理最不活跃的用户"""
        if not self.user_profiles:
            return
        
        sorted_users = sorted(
            self.user_profiles.items(),
            key=lambda x: x[1].last_seen
        )
        
        remove_count = len(self.user_profiles) - self.max_users // 2
        for i in range(remove_count):
            if i < len(sorted_users):
                del self.user_profiles[sorted_users[i][0]]
    
    def analyze_danmaku(self, 
                        username: str, 
                        content: str, 
                        timestamp: float,
                        room_id: int,
                        danmaku_id: Optional[str] = None) -> DanmakuAnalysis:
        """
        分析单条弹幕
        """
        if danmaku_id is None:
            danmaku_id = hashlib.md5(f"{username}{content}{timestamp}".encode()).hexdigest()[:12]
        
        sentiment_score, sentiment_type = self.analyze_sentiment(content)
        keywords = self.extract_keywords(content, topK=5)
        words = self.segment_text(content)
        word_count = len(words)
        
        is_duplicate, duplicate_count, duplicate_group_id = self.detect_duplicate(
            content, timestamp, username
        )
        
        is_suspicious, suspicious_reason = self.detect_suspicious_behavior(
            username, content, timestamp
        )
        
        analysis = DanmakuAnalysis(
            danmaku_id=danmaku_id,
            username=username,
            content=content,
            timestamp=timestamp,
            room_id=room_id,
            sentiment_score=sentiment_score,
            sentiment_type=sentiment_type,
            keywords=keywords,
            word_count=word_count,
            is_duplicate=is_duplicate,
            duplicate_count=duplicate_count,
            duplicate_group_id=duplicate_group_id,
            is_suspicious=is_suspicious,
            suspicious_reason=suspicious_reason
        )
        
        with self._lock:
            self.danmaku_history.append(analysis)
            if len(self.danmaku_history) > self.max_history:
                self.danmaku_history = self.danmaku_history[-self.max_history//2:]
        
        self.update_user_profile(username, analysis, timestamp)
        
        return analysis
    
    def get_word_frequency(self, 
                           time_window: Optional[int] = 3600,
                           top_n: int = 100) -> Dict[str, int]:
        """
        获取词频统计
        time_window: 时间窗口（秒），None表示全部历史
        """
        with self._lock:
            word_counter = Counter()
            
            if time_window is None:
                target_danmaku = self.danmaku_history
            else:
                cutoff_time = time.time() - time_window
                target_danmaku = [
                    d for d in self.danmaku_history 
                    if d.timestamp > cutoff_time
                ]
            
            for danmaku in target_danmaku:
                for keyword in danmaku.keywords:
                    word_counter[keyword] += 1
                
                words = self.segment_text(danmaku.content)
                for word in words:
                    if len(word) >= 2:
                        word_counter[word] += 1
            
            return dict(word_counter.most_common(top_n))
    
    def get_hot_topics(self, 
                       time_window: int = 3600,
                       top_n: int = 10) -> List[HotTopic]:
        """
        获取热门话题
        """
        with self._lock:
            word_freq = self.get_word_frequency(time_window=time_window, top_n=top_n * 2)
            
            cutoff_time = time.time() - time_window
            recent_danmaku = [
                d for d in self.danmaku_history 
                if d.timestamp > cutoff_time
            ]
            
            topics = []
            for keyword, count in word_freq.items():
                if len(keyword) < 2:
                    continue
                
                related = [
                    {
                        'username': d.username,
                        'content': d.content,
                        'timestamp': d.timestamp,
                        'sentiment': d.sentiment_type.value
                    }
                    for d in recent_danmaku[-50:]
                    if keyword in d.content or keyword in d.keywords
                ]
                
                recent_count = len([
                    d for d in recent_danmaku[-100:]
                    if keyword in d.content or keyword in d.keywords
                ])
                trend_score = recent_count / max(1, count)
                
                topics.append(HotTopic(
                    keyword=keyword,
                    count=count,
                    trend_score=trend_score,
                    related_danmaku=related[:10]
                ))
            
            topics.sort(key=lambda x: (x.trend_score, x.count), reverse=True)
            return topics[:top_n]
    
    def get_duplicate_stats(self, top_n: int = 20) -> List[Dict]:
        """
        获取重复弹幕统计
        """
        with self._lock:
            sorted_groups = sorted(
                self.duplicate_groups.values(),
                key=lambda x: x.count,
                reverse=True
            )
            
            result = []
            for group in sorted_groups[:top_n]:
                top_users = group.users.most_common(5)
                result.append({
                    'content_hash': group.content_hash,
                    'content_sample': group.content_sample,
                    'count': group.count,
                    'top_users': [{'username': u, 'count': c} for u, c in top_users],
                    'first_seen': group.first_seen,
                    'last_seen': group.last_seen,
                    'avg_sentiment': group.avg_sentiment,
                    'time_span': group.last_seen - group.first_seen
                })
            
            return result
    
    def get_sentiment_stats(self, time_window: Optional[int] = 3600) -> Dict:
        """
        获取情感统计
        """
        with self._lock:
            if time_window is None:
                target_danmaku = self.danmaku_history
            else:
                cutoff_time = time.time() - time_window
                target_danmaku = [
                    d for d in self.danmaku_history 
                    if d.timestamp > cutoff_time
                ]
            
            positive_count = sum(1 for d in target_danmaku if d.sentiment_type == SentimentType.POSITIVE)
            neutral_count = sum(1 for d in target_danmaku if d.sentiment_type == SentimentType.NEUTRAL)
            negative_count = sum(1 for d in target_danmaku if d.sentiment_type == SentimentType.NEGATIVE)
            
            total = len(target_danmaku)
            avg_sentiment = sum(d.sentiment_score for d in target_danmaku) / total if total > 0 else 0.5
            
            return {
                'total': total,
                'positive': positive_count,
                'neutral': neutral_count,
                'negative': negative_count,
                'positive_ratio': positive_count / total if total > 0 else 0,
                'neutral_ratio': neutral_count / total if total > 0 else 0,
                'negative_ratio': negative_count / total if total > 0 else 0,
                'avg_sentiment': avg_sentiment,
                'time_window_seconds': time_window
            }
    
    def get_active_users(self, 
                         time_window: int = 3600,
                         top_n: int = 20) -> List[Dict]:
        """
        获取活跃用户统计
        """
        with self._lock:
            cutoff_time = time.time() - time_window
            
            user_activity = defaultdict(lambda: {
                'count': 0,
                'positive': 0,
                'neutral': 0,
                'negative': 0,
                'keywords': Counter(),
                'last_seen': 0
            })
            
            for danmaku in self.danmaku_history:
                if danmaku.timestamp > cutoff_time:
                    activity = user_activity[danmaku.username]
                    activity['count'] += 1
                    activity['last_seen'] = danmaku.timestamp
                    
                    if danmaku.sentiment_type == SentimentType.POSITIVE:
                        activity['positive'] += 1
                    elif danmaku.sentiment_type == SentimentType.NEGATIVE:
                        activity['negative'] += 1
                    else:
                        activity['neutral'] += 1
                    
                    for keyword in danmaku.keywords:
                        activity['keywords'][keyword] += 1
            
            sorted_users = sorted(
                user_activity.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )
            
            result = []
            for username, activity in sorted_users[:top_n]:
                profile = self.user_profiles.get(username)
                
                total = activity['count']
                result.append({
                    'username': username,
                    'total_danmaku': total,
                    'positive': activity['positive'],
                    'neutral': activity['neutral'],
                    'negative': activity['negative'],
                    'positive_ratio': activity['positive'] / total if total > 0 else 0,
                    'negative_ratio': activity['negative'] / total if total > 0 else 0,
                    'top_keywords': [{'word': w, 'count': c} for w, c in activity['keywords'].most_common(5)],
                    'last_seen': activity['last_seen'],
                    'avg_sentiment': profile.avg_sentiment if profile else 0.5,
                    'duplicate_ratio': profile.duplicate_ratio if profile else 0.0
                })
            
            return result
    
    def get_suspicious_users(self, time_window: int = 3600) -> List[Dict]:
        """
        获取可疑用户（潜在带节奏者）
        """
        with self._lock:
            cutoff_time = time.time() - time_window
            
            suspicious = []
            for username, profile in self.user_profiles.items():
                if profile.last_seen < cutoff_time:
                    continue
                
                risk_score = 0.0
                
                if profile.duplicate_ratio > 0.5:
                    risk_score += 0.3
                
                if profile.avg_sentiment < 0.4 and profile.total_danmaku > 5:
                    risk_score += 0.3
                
                if profile.total_danmaku > 20:
                    risk_score += 0.2
                
                recent_negative = sum(
                    1 for d in self.danmaku_history[-100:]
                    if d.username == username 
                    and d.timestamp > cutoff_time
                    and d.sentiment_type == SentimentType.NEGATIVE
                )
                if recent_negative >= 5:
                    risk_score += 0.4
                
                if risk_score >= 0.5:
                    suspicious.append({
                        'username': username,
                        'risk_score': risk_score,
                        'total_danmaku': profile.total_danmaku,
                        'avg_sentiment': profile.avg_sentiment,
                        'duplicate_ratio': profile.duplicate_ratio,
                        'recent_negative_count': recent_negative,
                        'last_seen': profile.last_seen
                    })
            
            suspicious.sort(key=lambda x: x['risk_score'], reverse=True)
            return suspicious
    
    def generate_wordcloud_data(self, 
                                 time_window: int = 3600,
                                 max_words: int = 100) -> Dict[str, Any]:
        """
        生成词云数据（供前端使用）
        """
        word_freq = self.get_word_frequency(time_window=time_window, top_n=max_words)
        
        filtered_freq = {}
        for word, count in word_freq.items():
            if len(word) >= 2 and count >= 2:
                filtered_freq[word] = count
        
        return {
            'words': [{'text': w, 'value': c} for w, c in filtered_freq.items()],
            'total_words': len(filtered_freq),
            'time_window_seconds': time_window
        }
    
    def get_realtime_stats(self) -> Dict:
        """
        获取实时统计概览
        """
        with self._lock:
            sentiment_1h = self.get_sentiment_stats(time_window=3600)
            sentiment_5m = self.get_sentiment_stats(time_window=300)
            
            hot_topics = self.get_hot_topics(time_window=3600, top_n=5)
            duplicate_stats = self.get_duplicate_stats(top_n=5)
            active_users = self.get_active_users(time_window=3600, top_n=5)
            suspicious_users = self.get_suspicious_users(time_window=3600)
            
            return {
                'timestamp': time.time(),
                'total_danmaku_analyzed': len(self.danmaku_history),
                'sentiment': {
                    'last_hour': sentiment_1h,
                    'last_5min': sentiment_5m
                },
                'hot_topics': [
                    {'keyword': t.keyword, 'count': t.count, 'trend_score': t.trend_score}
                    for t in hot_topics
                ],
                'duplicate_stats': duplicate_stats,
                'active_users': active_users,
                'suspicious_users': suspicious_users[:5],
                'suspicious_count': len(suspicious_users)
            }
    
    def clear_history(self):
        """
        清空历史数据
        """
        with self._lock:
            self.danmaku_history.clear()
            self.user_profiles.clear()
            self.duplicate_groups.clear()
            self.content_hash_map.clear()
            logging.info("弹幕分析历史数据已清空")


_danmaku_analyzer_instance = None


def get_danmaku_analyzer() -> DanmakuAnalyzer:
    """获取全局弹幕分析器实例"""
    global _danmaku_analyzer_instance
    if _danmaku_analyzer_instance is None:
        _danmaku_analyzer_instance = DanmakuAnalyzer()
    return _danmaku_analyzer_instance
