"""
弹幕评分服务
提供弹幕评分集成到现有评分机制的功能
"""

import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass, asdict

from utils.danmaku_analyzer import DanmakuAnalyzer, load_analysis_result, DanmakuAnalysisResult

if TYPE_CHECKING:
    from models.danmaku import DanmakuFile, DanmakuFileStatus

logger = logging.getLogger(__name__)


@dataclass
class DanmakuScoreBreakdown:
    """弹幕评分细项"""
    heat_score: float = 0.0
    keyword_score: float = 0.0
    sentiment_score: float = 0.0
    special_score: float = 0.0
    total_danmaku_score: float = 0.0
    
    heat_contribution: float = 0.0
    keyword_contribution: float = 0.0
    sentiment_contribution: float = 0.0
    special_contribution: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DanmakuScoreService:
    """弹幕评分服务"""
    
    def __init__(self, 
                 heat_weight: float = 0.4,
                 keyword_weight: float = 0.2,
                 sentiment_weight: float = 0.2,
                 special_weight: float = 0.2,
                 danmaku_total_weight: float = 0.3):
        """
        初始化弹幕评分服务
        
        Args:
            heat_weight: 热度维度权重
            keyword_weight: 关键词维度权重
            sentiment_weight: 情感维度权重
            special_weight: 特殊弹幕维度权重
            danmaku_total_weight: 弹幕评分在总分中的权重（0-1）
        """
        self.heat_weight = heat_weight
        self.keyword_weight = keyword_weight
        self.sentiment_weight = sentiment_weight
        self.special_weight = special_weight
        self.danmaku_total_weight = danmaku_total_weight
        
        self.analyzer = DanmakuAnalyzer()
    
    def get_danmaku_score_for_clip(self,
                                    start_time: float,
                                    end_time: float,
                                    analysis_result: DanmakuAnalysisResult) -> DanmakuScoreBreakdown:
        """
        获取指定时间范围的弹幕评分
        
        Args:
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            analysis_result: 弹幕分析结果
            
        Returns:
            DanmakuScoreBreakdown: 弹幕评分细项
        """
        if not analysis_result or not analysis_result.heat_points:
            return DanmakuScoreBreakdown()
        
        scores = self.analyzer.get_score_for_time_range(
            start_time, end_time, analysis_result
        )
        
        heat_score = scores.get('heat_score', 0.0)
        keyword_score = scores.get('keyword_score', 0.0)
        sentiment_score = scores.get('sentiment_score', 0.0)
        special_score = scores.get('special_score', 0.0)
        
        weighted_total = (
            heat_score * self.heat_weight +
            keyword_score * self.keyword_weight +
            sentiment_score * self.sentiment_weight +
            special_score * self.special_weight
        )
        
        breakdown = DanmakuScoreBreakdown(
            heat_score=heat_score,
            keyword_score=keyword_score,
            sentiment_score=sentiment_score,
            special_score=special_score,
            total_danmaku_score=weighted_total,
            heat_contribution=heat_score * self.heat_weight * self.danmaku_total_weight,
            keyword_contribution=keyword_score * self.keyword_weight * self.danmaku_total_weight,
            sentiment_contribution=sentiment_score * self.sentiment_weight * self.danmaku_total_weight,
            special_contribution=special_score * self.special_weight * self.danmaku_total_weight
        )
        
        return breakdown
    
    def combine_with_llm_score(self,
                                llm_score: float,
                                danmaku_breakdown: DanmakuScoreBreakdown) -> Dict[str, Any]:
        """
        组合 LLM 评分和弹幕评分
        
        Args:
            llm_score: LLM 原始评分（0-100）
            danmaku_breakdown: 弹幕评分细项
            
        Returns:
            包含组合评分的字典
        """
        llm_weight = 1.0 - self.danmaku_total_weight
        danmaku_contribution = danmaku_breakdown.total_danmaku_score * self.danmaku_total_weight
        
        combined_score = (
            llm_score * llm_weight +
            danmaku_contribution
        )
        
        combined_score = max(0.0, min(100.0, combined_score))
        
        return {
            'original_llm_score': llm_score,
            'danmaku_score_breakdown': danmaku_breakdown.to_dict(),
            'llm_weight': llm_weight,
            'danmaku_weight': self.danmaku_total_weight,
            'danmaku_contribution': danmaku_contribution,
            'combined_score': round(combined_score, 2)
        }
    
    def enhance_clip_with_danmaku_score(self,
                                         clip_data: Dict[str, Any],
                                         analysis_result: DanmakuAnalysisResult) -> Dict[str, Any]:
        """
        为切片数据添加弹幕评分
        
        Args:
            clip_data: 原始切片数据（需包含 start_time 和 end_time）
            analysis_result: 弹幕分析结果
            
        Returns:
            添加了弹幕评分的切片数据
        """
        start_time = clip_data.get('start_time', 0)
        end_time = clip_data.get('end_time', 0)
        
        if start_time >= end_time:
            duration = clip_data.get('duration', 0)
            if duration > 0:
                end_time = start_time + duration
        
        danmaku_breakdown = self.get_danmaku_score_for_clip(
            start_time, end_time, analysis_result
        )
        
        original_score = clip_data.get('final_score', 50)
        
        combined = self.combine_with_llm_score(original_score, danmaku_breakdown)
        
        clip_data['danmaku_score'] = combined['danmaku_score_breakdown']
        clip_data['original_llm_score'] = original_score
        clip_data['final_score'] = int(round(combined['combined_score']))
        clip_data['score_breakdown'] = {
            'llm_score': original_score,
            'danmaku_score': combined['danmaku_score_breakdown']['total_danmaku_score'],
            'llm_weight': combined['llm_weight'],
            'danmaku_weight': combined['danmaku_weight'],
            'danmaku_contribution': combined['danmaku_contribution'],
            'combined_score': combined['combined_score']
        }
        
        logger.info(
            f"切片评分增强: 原始LLM分数={original_score}, "
            f"弹幕分数={danmaku_breakdown.total_danmaku_score:.2f}, "
            f"最终分数={clip_data['final_score']}"
        )
        
        return clip_data


def load_danmaku_analysis_from_file(analysis_file_path: str) -> Optional[DanmakuAnalysisResult]:
    """
    从文件加载弹幕分析结果
    
    Args:
        analysis_file_path: 分析结果文件路径
        
    Returns:
        DanmakuAnalysisResult 或 None
    """
    try:
        path = Path(analysis_file_path)
        if not path.exists():
            logger.warning(f"弹幕分析文件不存在: {analysis_file_path}")
            return None
        
        return load_analysis_result(str(path))
        
    except Exception as e:
        logger.error(f"加载弹幕分析结果失败: {e}")
        return None


def get_danmaku_analysis_from_db(danmaku_file: 'DanmakuFile') -> Optional[DanmakuAnalysisResult]:
    """
    从数据库记录获取弹幕分析结果
    
    Args:
        danmaku_file: 弹幕文件数据库记录
        
    Returns:
        DanmakuAnalysisResult 或 None
    """
    from models.danmaku import DanmakuFileStatus
    
    if not danmaku_file:
        return None
    
    if danmaku_file.status != DanmakuFileStatus.ANALYZED:
        logger.warning(f"弹幕文件尚未分析: {danmaku_file.id}")
        return None
    
    if not danmaku_file.analysis_metadata or 'analysis_file' not in danmaku_file.analysis_metadata:
        logger.warning(f"弹幕文件缺少分析文件路径: {danmaku_file.id}")
        return None
    
    analysis_file = danmaku_file.analysis_metadata['analysis_file']
    return load_danmaku_analysis_from_file(analysis_file)
