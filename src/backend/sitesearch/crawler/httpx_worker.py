"""
基于HTTPX的爬虫实现
提供HTTP爬取功能的具体实现
"""

import httpx
import logging
import re
import time
import os
import hashlib
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional, Tuple, Set
from urllib.parse import urljoin, urlparse, unquote
import xml.etree.ElementTree as ET
import threading

from .base_crawler import BaseCrawler
from ..handler.base_handler import SkipError
from ..utils.mime import PLAIN_TEXT_MIMETYPES, BINARY_MIMETYPES

# 配置日志
logger = logging.getLogger('httpx_worker')

class HttpxWorker(BaseCrawler):
    """
    基于HTTPX的爬虫实现，提供HTTP请求和HTML解析功能
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化HTTPX爬虫
        
        Args:
            base_url: str,
            max_urls: int = 100,
            max_depth: int = 3,
            request_delay: float = 0.5,
            headers: Optional[Dict[str, str]] = None,
            cookies: Optional[Dict[str, str]] = None,
            excluded_patterns: Optional[List[str]] = None,
            included_patterns: Optional[List[str]] = None,
            proxy: Optional[str] = None,
            timeout: int = 30,
            verify_ssl: bool = True,
            follow_redirects: bool = True,
            on_page_crawled: Optional[Callable[[str, str, Dict[str, Any]], None]] = None
        """
        super().__init__(*args, **kwargs)
        
        # 创建HTTPX客户端
        self.client = self._create_client()
        
        # 元数据收集器
        self.metadata_collectors = [
            self._collect_title,
            self._collect_meta_tags,
            self._collect_headings,
            self._collect_image_alts,
        ]
        
        # 爬虫锁，用于线程安全操作
        self.lock = threading.Lock()
    
    def _create_client(self) -> httpx.Client:
        """
        创建HTTPX客户端
        
        Returns:
            httpx.Client: 配置好的HTTPX客户端
        """
        # 设置更细粒度的超时控制
        timeout_config = httpx.Timeout(
            connect=self.timeout,  # 连接超时
            read=self.timeout * 2,  # 读取超时设置更长
            write=self.timeout,  # 写入超时
            pool=self.timeout * 3  # 连接池超时设置最长
        )

        limits = httpx.Limits(max_keepalive_connections=1000, max_connections=1000, keepalive_expiry=30)
        
        # 客户端选项
        client_options = {
            "headers": self.headers,
            "cookies": self.cookies,
            "timeout": timeout_config,
            "limits": limits,
            "verify": self.verify_ssl,
            "follow_redirects": self.follow_redirects,
        }
        
        # 如果设置了代理，添加代理配置
        if self.proxy:
            client_options["proxies"] = {
                "http://": self.proxy,
                "https://": self.proxy
            }
        
        return httpx.Client(**client_options)
    
    def extract_links(self, url: str, html_content: str) -> List[str]:
        """
        从HTML内容中提取链接
        
        Args:
            url: 当前页面的URL
            html_content: HTML内容
            
        Returns:
            List[str]: 提取到的链接列表
        """
        try:
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取所有a标签的href属性
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href')
                if href:
                    # 过滤掉JavaScript链接和空链接
                    if href.startswith('javascript:') or href == '#':
                        continue
                    links.append(href)
            
            # 将链接转换为绝对路径
            return [urljoin(url, link) for link in links]
        
        except Exception as e:
            logger.error(f"提取链接时出错: {str(e)}")
            return []
    
    def get_title(self, response: httpx.Response) -> str:
        """获取网页标题"""
        try:
            tree = BeautifulSoup(response.text, 'html.parser')
            # 从url中获取title
            url = urlparse(str(response.url))
            if url.path and '/' in url.path:
                tail_path = url.path.split('/')[-1]
                basename = os.path.basename(tail_path) if '.' in tail_path else tail_path
                basename = basename.replace('.html', '').replace('.pdf', '')
                # 转义回正常字符串
                basename = unquote(basename)
                basename = (basename[:245] + '...') if len(basename) > 250 else basename
                return basename if not tree.title else (tree.title.text[:245] + '...') if len(tree.title.text) > 250 else tree.title.text
            else:
                title = tree.title.text if tree.title else url.netloc
                return (title[:245] + '...') if len(title) > 250 else title
        except Exception as e:
            logger.error(f"获取标题时出错: {str(e)}")
            return "未知标题"
    
    def get_related_links(self, url: str, response: httpx.Response) -> List[str]:
        """获取网页相关链接"""
        try:
            tree = BeautifulSoup(response.text, 'html.parser')
            links = [link.get('href') for link in tree.find_all('a') if link.get('href')]
            # 过滤掉javascript:void(0)类型的链接
            valid_links = [link for link in links if not link.startswith('javascript:')]
            # 将链接转换为绝对路径
            return [urljoin(url, link) for link in valid_links if link]
        except Exception as e:
            logger.error(f"获取相关链接时出错: {str(e)}")
            return []
    
    def crawl_page(self, url: str) -> Dict[str, Any]:
        """
        爬取单个页面
        
        Args:
            url: 要爬取的URL
            
        Returns:
            Dict[str, Any]: 包含页面内容和元数据的字典
        """
        url = self.normalize_url(url)
        result = {
            "url": url,
            "content": "",
            "status_code": 0,
            "headers": {},
            "timestamp": time.time(),
            "links": [],
            "mimetype": "",
            "metadata": {}
        }
        
        try:
            # 发送HTTP请求
            response = self.client.get(url)

            if response.status_code // 100 == 4:
                # 4xx错误，跳过
                raise SkipError(f"HTTP错误: {response.status_code}")
            elif response.status_code // 100 == 5:
                # 5xx错误，跳过
                raise SkipError(f"HTTP错误: {response.status_code}")
            
            # response.raise_for_status()  # 如果响应码不是2xx，抛出异常
            
            # 记录基本信息
            result["status_code"] = response.status_code
            result["headers"] = dict(response.headers)
            
            # 获取内容类型
            content_type = response.headers.get('content-type', 'text/html')
            result["mimetype"] = content_type

            if any(content_type.startswith(mimetype) for mimetype in PLAIN_TEXT_MIMETYPES):
                result["content"] = response.text
                result["links"] = self.get_related_links(url, response)
            elif any(content_type.startswith(mimetype) for mimetype in BINARY_MIMETYPES):
                result["content"] = response.content
            else:
                raise SkipError(f"不支持的内容类型: {content_type}")

            # 提取域名作为source
            domain = urlparse(url).netloc
            
            # 收集元数据
            metadata = {
                "source": domain,
                "url": url,
                "title": self.get_title(response),
                "timestamp": time.time(),
            }
            
            # 获取更多元数据
            for collector in self.metadata_collectors:
                try:
                    collector_result = collector(response.text)
                    if collector_result:
                        metadata.update(collector_result)
                except Exception as e:
                    logger.error(f"收集元数据时出错 ({collector.__name__}): {str(e)}")
            
            result["metadata"] = metadata
            
            # 计算内容哈希值，可用于比较内容是否变化
            if isinstance(result["content"], str):
                result["content_hash"] = hashlib.sha256(result["content"].encode()).hexdigest()
            elif isinstance(result["content"], bytes):
                result["content_hash"] = hashlib.sha256(result["content"]).hexdigest()
            else:
                raise SkipError(f"不支持的内容类型: {type(result['content'])}")
            
            return result
        except SkipError as e:
            logger.info(f"由于 {url} 错误码 {response.status_code} 跳过")
            raise e
        except httpx.RequestError as e:
            logger.error(f"请求 {url} 失败: {str(e)}")
            result["error"] = f"请求失败: {str(e)}"
            raise
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP错误 {url}: {e.response.status_code}")
            result["status_code"] = e.response.status_code
            result["error"] = f"HTTP错误: {e.response.status_code}"
            raise
        
        except Exception as e:
            logger.error(f"未知错误 {url}: {str(e)}")
            result["error"] = f"未知错误: {str(e)}"
            raise e
    
    def discover_sitemap(self) -> List[str]:
        """
        尝试发现并解析网站的sitemap
        
        Returns:
            List[str]: 从sitemap中提取的URL列表
        """
        sitemap_urls = []
        
        # 常见的sitemap路径
        sitemap_paths = [
            "sitemap.xml",
            "sitemap_index.xml",
            "sitemap/sitemap.xml",
            "sitemaps/sitemap.xml",
        ]
        
        # 尝试获取每个可能的sitemap
        for path in sitemap_paths:
            try:
                # 构建完整的sitemap URL
                sitemap_url = path if "://" in path else urljoin(self.base_url, path)
                
                response = self.client.get(sitemap_url)
                if response.is_success:
                    urls = self._parse_sitemap(response.text)
                    sitemap_urls.extend(urls)
                    logger.info(f"从 {sitemap_url} 提取到 {len(urls)} 个URL")
            
            except Exception as e:
                logger.error(f"处理sitemap {path} 失败: {str(e)}")
        
        return sitemap_urls
    
    def _parse_sitemap(self, content: str) -> List[str]:
        """
        解析sitemap XML内容
        
        Args:
            content: sitemap XML内容
            
        Returns:
            List[str]: 从sitemap中提取的URL列表
        """
        urls = []
        
        try:
            # 移除XML命名空间，简化解析
            content = re.sub(r'\sxmlns="[^"]+"', '', content)
            root = ET.fromstring(content)
            
            # 解析sitemap索引文件
            for sitemap in root.findall(".//sitemap"):
                loc = sitemap.find("loc")
                if loc is not None and loc.text:
                    try:
                        response = self.client.get(loc.text)
                        if response.is_success:
                            urls.extend(self._parse_sitemap(response.text))
                    except Exception as e:
                        logger.error(f"获取子sitemap失败 {loc.text}: {str(e)}")
            
            # 解析普通sitemap
            for url in root.findall(".//url"):
                loc = url.find("loc")
                if loc is not None and loc.text:
                    urls.append(loc.text)
        
        except Exception as e:
            logger.error(f"解析sitemap失败: {str(e)}")
        
        return urls
    
    def add_url(self, url: str, depth: int = 0) -> None:
        """
        添加URL到爬取队列
        
        Args:
            url: 要添加的URL
            depth: URL的深度
        """
        if self.is_valid_url(url) and url not in self.crawled_urls:
            with self.lock:
                # 检查队列中是否已有此URL
                if not any(item["url"] == url for item in self.url_queue):
                    self.url_queue.append({
                        "url": url,
                        "depth": depth
                    })
                    logger.debug(f"添加URL到队列: {url}")
        else:
            if not self.is_valid_url(url):
                logger.error(f"无效的URL: {url}")
            if url in self.crawled_urls:
                logger.info(f"URL已爬取: {url}")
    
    def _collect_title(self, html_content: str) -> Dict[str, str]:
        """
        从HTML中提取标题
        
        Args:
            html_content: HTML内容
            
        Returns:
            Dict[str, str]: 包含标题的字典
        """
        metadata = {}
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            title_tag = soup.find('title')
            if title_tag and title_tag.text:
                metadata['title'] = title_tag.text.strip()
        except Exception:
            pass
        return metadata
    
    def _collect_meta_tags(self, html_content: str) -> Dict[str, str]:
        """
        从HTML中提取meta标签信息
        
        Args:
            html_content: HTML内容
            
        Returns:
            Dict[str, str]: 包含meta标签信息的字典
        """
        metadata = {}
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 收集description和keywords
            for meta in soup.find_all('meta'):
                name = meta.get('name', '').lower()
                content = meta.get('content', '')
                
                if name in ['description', 'keywords'] and content:
                    metadata[f'meta_{name}'] = content
                
                # 收集Open Graph标签
                property_name = meta.get('property', '').lower()
                if property_name.startswith('og:') and content:
                    og_name = property_name[3:]  # 移除'og:'前缀
                    metadata[f'og_{og_name}'] = content
        
        except Exception:
            pass
        return metadata
    
    def _collect_headings(self, html_content: str) -> Dict[str, Any]:
        """
        从HTML中提取标题(h1-h6)内容
        
        Args:
            html_content: HTML内容
            
        Returns:
            Dict[str, Any]: 包含标题内容的字典
        """
        metadata = {}
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 收集h1-h6标签内容
            for level in range(1, 7):
                tag_name = f'h{level}'
                headings = soup.find_all(tag_name)
                if headings:
                    metadata[f'headings_h{level}'] = [h.text.strip() for h in headings if h.text.strip()]
        
        except Exception:
            pass
        return metadata
    
    def _collect_image_alts(self, html_content: str) -> Dict[str, List[Dict[str, str]]]:
        """
        从HTML中提取图片及其alt文本
        
        Args:
            html_content: HTML内容
            
        Returns:
            Dict[str, List[Dict[str, str]]]: 包含图片信息的字典
        """
        metadata = {}
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            images = []
            for img in soup.find_all('img'):
                src = img.get('src', '')
                alt = img.get('alt', '')
                if src:
                    images.append({
                        'src': src,
                        'alt': alt
                    })
            
            if images:
                metadata['images'] = images
        
        except Exception:
            pass
        return metadata
    
    def close(self):
        """
        关闭爬虫并释放资源
        """
        if hasattr(self, 'client') and self.client:
            self.client.close()
            logger.info("HTTPX客户端已关闭") 