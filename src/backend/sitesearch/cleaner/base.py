from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Dict, Optional, Union
from datetime import datetime
import httpx
import json

@dataclass
class CrawlerMetadata:
    """爬虫元数据类"""
    source: str  # 数据来源
    url: Optional[str] = None  # URL（如果适用）
    title: Optional[str] = None  # 标题
    date: Optional[datetime] = None  # 日期
    related_links: Optional[List[str]] = None  # 相关链接
    extra: Optional[Dict[str, Any]] = None  # 额外元数据

    def to_dict(self):
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat() if value else None
            elif value is not None:
                result[key] = value
        return result

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

@dataclass
class CrawlerResult:
    """爬虫结果类"""
    mimetype: str  # 内容类型
    content: str  # 清洗后的内容
    metadata: CrawlerMetadata  # 元数据
    raw_data: Any  # 原始数据

    def to_dict(self):
        """转换为字典格式"""
        return {
            'mimetype': self.mimetype,
            'content': self.content,
            'metadata': self.metadata.to_dict() if self.metadata else None,
            'raw_data': self.raw_data
        }

    def to_json(self):
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def __hash__(self) -> int:
        return hash(self.content)

class DataCleaner(ABC):
    """数据清洗器基类"""
    
    @abstractmethod
    def clean(self, data: Any) -> Any:
        """清洗数据的抽象方法
        
        Args:
            data: 需要清洗的数据
            
        Returns:
            清洗后的数据
        """
        pass

class DataCrawler(ABC):
    """数据采集器基类"""
    
    def __init__(self):
        self.cleaners: List[DataCleaner] = []
    
    def add_cleaner(self, cleaner: Union[DataCleaner, List[DataCleaner]]) -> None:
        """添加数据清洗器
        
        Args:
            cleaner: 数据清洗器实例
        """
        if isinstance(cleaner, list):
            self.cleaners.extend(cleaner)
        else:
            self.cleaners.append(cleaner)
    
    @abstractmethod
    def crawl(self, **kwargs) -> CrawlerResult:
        """采集数据的抽象方法
        
        Returns:
            包含清洗后内容和元数据的CrawlerResult对象
        """
        pass 

class CleaningStrategy:
    """清洗策略基类"""
    
    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        """判断是否应该使用此策略处理内容
        
        Args:
            url: 内容的URL
            mimetype: 内容的MIME类型
            content: 原始内容
            
        Returns:
            是否应该使用此策略
        """
        return False
        
    def clean(self, content: bytes | str) -> str:
        """清洗内容
        
        Args:
            content: 原始内容
            
        Returns:
            清洗后的内容
        """
        raise NotImplementedError() 
    
class NoStrategyMatch(Exception):
    """没有匹配的策略"""
    pass
