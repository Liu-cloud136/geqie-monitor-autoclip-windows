"""
基础服务类
提供通用的业务逻辑操作
"""

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from repositories.base import BaseRepository, ModelType as RepoModelType
from schemas.base import BaseSchema, PaginationParams, PaginationResponse


DEFAULT_PAGE_SKIP = 0
DEFAULT_PAGE_LIMIT = 100


CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")
ResponseSchemaType = TypeVar("ResponseSchemaType")


class BaseService(Generic[RepoModelType, CreateSchemaType, UpdateSchemaType, ResponseSchemaType]):
    """
    基础服务类
    
    提供通用的CRUD操作，包括创建、读取、更新、删除、分页查询等功能
    
    Generic Types:
        RepoModelType: 模型类型
        CreateSchemaType: 创建模式类型
        UpdateSchemaType: 更新模式类型
        ResponseSchemaType: 响应模式类型
    
    Attributes:
        repository: 数据仓库实例
    """
    
    def __init__(self, repository: BaseRepository[RepoModelType]):
        """
        初始化基础服务
        
        Args:
            repository: 数据仓库实例
        """
        self.repository = repository
    
    def get(self, id: str) -> Optional[RepoModelType]:
        """
        根据ID获取单条记录
        
        Args:
            id: 记录ID
            
        Returns:
            模型实例，如果不存在则返回None
        """
        return self.repository.get_by_id(id)
    
    def get_multi(
        self, 
        skip: int = DEFAULT_PAGE_SKIP, 
        limit: int = DEFAULT_PAGE_LIMIT,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RepoModelType]:
        """
        获取多条记录（支持过滤）
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数限制
            filters: 过滤条件字典
            
        Returns:
            模型实例列表
        """
        if filters:
            return self.repository.find_by(**filters)
        return self.repository.get_all(skip=skip, limit=limit)
    
    def create(self, **kwargs) -> RepoModelType:
        """
        创建新记录
        
        Args:
            **kwargs: 模型字段和值
            
        Returns:
            创建的模型实例
        """
        return self.repository.create(**kwargs)
    
    def update(self, id: str, **kwargs) -> Optional[RepoModelType]:
        """
        更新现有记录
        
        Args:
            id: 记录ID
            **kwargs: 要更新的字段和值
            
        Returns:
            更新后的模型实例，如果不存在则返回None
        """
        return self.repository.update(id, **kwargs)
    
    def delete(self, id: str) -> bool:
        """
        删除记录
        
        Args:
            id: 记录ID
            
        Returns:
            是否删除成功
        """
        return self.repository.delete(id)
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        统计记录数量（支持过滤）
        
        Args:
            filters: 过滤条件字典
            
        Returns:
            记录数量
        """
        if filters:
            return len(self.repository.find_by(**filters))
        return self.repository.count()
    
    def exists(self, id: str) -> bool:
        """
        检查记录是否存在
        
        Args:
            id: 记录ID
            
        Returns:
            是否存在
        """
        return self.repository.exists(id)
    
    def get_paginated(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[List[RepoModelType], PaginationResponse]:
        """
        获取分页结果
        
        Args:
            pagination: 分页参数
            filters: 过滤条件字典
            
        Returns:
            包含模型实例列表和分页响应的元组
        """
        skip = (pagination.page - 1) * pagination.size
        limit = pagination.size
        
        items = self.get_multi(skip=skip, limit=limit, filters=filters)
        total = self.count(filters)
        
        pages = (total + pagination.size - 1) // pagination.size
        has_next = pagination.page < pages
        has_prev = pagination.page > 1
        
        pagination_response = PaginationResponse(
            page=pagination.page,
            size=pagination.size,
            total=total,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return items, pagination_response