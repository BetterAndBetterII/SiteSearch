"""
真实网站爬取测试模块
测试爬虫对真实网站的抓取能力
"""

import os
import sys
import unittest
import time
from typing import Dict, Any

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.backend.sitesearch.crawler.httpx_worker import HttpxWorker


class TestRealWebsiteCrawler(unittest.TestCase):
    """真实网站爬取测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 定义测试的基础URL
        self.base_url = "https://www.cuhk.edu.cn"
        
        # 创建爬虫实例
        self.crawler = HttpxWorker(
            base_url=self.base_url,
            max_urls=10,
            max_depth=2,
            request_delay=1.0,  # 设置较长的延迟，避免请求过于频繁
            timeout=30  # 增加超时时间
        )
    
    def tearDown(self):
        """测试后的清理工作"""
        # 关闭爬虫
        self.crawler.close()
    
    def test_homepage_crawl(self):
        """测试爬取大学首页"""
        # 爬取首页
        url = "https://www.cuhk.edu.cn/zh-hans"
        result = self.crawler.crawl_page(url)
        
        # 验证基本信息
        self.assertIsNotNone(result)
        self.assertEqual(result["url"], url)
        self.assertEqual(result["status_code"], 200)
        
        # 打印标题，帮助调试
        print(f"\n获取到的页面标题: {result['metadata'].get('title', '无标题')}")
        
        # 验证内容 - 使用更灵活的检查方式
        content = result["content"]
        expected_keywords = ["香港中文大学", "深圳"]
        for keyword in expected_keywords:
            self.assertIn(keyword, content, f"内容中未找到关键词: {keyword}")
        
        # 验证元数据
        self.assertIn("title", result["metadata"])
        
        # 验证提取的链接
        self.assertIn("related_links", result["metadata"])
        self.assertTrue(len(result["metadata"]["related_links"]) > 0, "未提取到任何链接")
        print(f"提取的链接数量: {len(result['metadata']['related_links'])}")
    
    def test_about_us_page(self):
        """测试爬取'关于我们'页面"""
        # 爬取关于我们页面
        url = "https://www.cuhk.edu.cn/zh-hans/about-us"
        try:
            result = self.crawler.crawl_page(url)
            
            # 验证基本信息
            self.assertIsNotNone(result)
            self.assertEqual(result["url"], url)
            self.assertEqual(result["status_code"], 200)
            
            # 验证内容 - 关键词检查
            content = result["content"]
            keywords = ["香港中文大学", "深圳", "教育", "大学"]
            found_keywords = 0
            for keyword in keywords:
                if keyword in content:
                    found_keywords += 1
            
            # 至少应该找到50%的关键词
            self.assertGreaterEqual(found_keywords, len(keywords) // 2, 
                                   f"在'关于我们'页面只找到{found_keywords}/{len(keywords)}个关键词")
            
        except Exception as e:
            self.fail(f"爬取'关于我们'页面时出错: {str(e)}")
    
    def test_governing_board_page(self):
        """测试爬取'理事会'页面"""
        # 爬取理事会页面
        url = "https://www.cuhk.edu.cn/zh-hans/governing-board"
        try:
            result = self.crawler.crawl_page(url)
            
            # 验证基本信息
            self.assertIsNotNone(result)
            self.assertEqual(result["url"], url)
            
            # 检查状态码，可能是200或重定向
            self.assertIn(result["status_code"], [200, 301, 302, 307, 308], 
                         f"非预期的状态码: {result['status_code']}")
            
            if result["status_code"] == 200:
                # 验证内容 - 尝试找到关键词
                content = result["content"]
                possible_keywords = ["理事会", "管理", "领导", "成员"]
                found_any = False
                for keyword in possible_keywords:
                    if keyword in content:
                        found_any = True
                        break
                
                # 如果页面内容确实与理事会相关，那么应该找到至少一个关键词
                if not found_any:
                    print(f"警告: 在'理事会'页面未找到预期关键词。页面内容可能已更改。")
            
        except Exception as e:
            self.fail(f"爬取'理事会'页面时出错: {str(e)}")
    
    def test_links_extraction(self):
        """测试从页面提取链接的能力"""
        # 爬取首页
        url = "https://www.cuhk.edu.cn/zh-hans"
        result = self.crawler.crawl_page(url)
        
        # 验证提取的链接
        links = result["metadata"]["related_links"]
        
        # 打印一些链接，帮助调试
        print(f"\n提取的链接示例(最多5个):")
        for link in links[:5]:
            print(f"  - {link}")
        
        # 验证链接数量
        self.assertGreater(len(links), 5, "提取的链接数量过少")
        
        # 检查所有链接是否都是有效的URL格式
        for link in links:
            self.assertTrue(link.startswith("http"), f"无效链接格式: {link}")
    
    def test_content_cleaning(self):
        """测试内容清洗功能"""
        # 爬取首页
        url = "https://www.cuhk.edu.cn/zh-hans"
        result = self.crawler.crawl_page(url)
        
        # 获取清洗后的内容
        content = result["content"]
        
        # 验证清洗质量 - HTML标签应该被移除
        html_tags = ["<html", "<body", "<div", "<span", "<script", "<style"]
        for tag in html_tags:
            self.assertNotIn(tag, content, f"清洗后的内容仍包含HTML标签: {tag}")
        
        # 检查内容是否保留了关键信息
        self.assertTrue(len(content) > 100, "清洗后的内容太短")
        
        # 检查内容中是否包含一些预期的关键词
        expected_words = ["大学", "学院", "教育", "学生"]
        found_words = 0
        for word in expected_words:
            if word in content:
                found_words += 1
        
        self.assertGreater(found_words, 0, "清洗后的内容没有保留任何预期关键词")
    
    def test_metadata_extraction(self):
        """测试元数据提取功能"""
        # 爬取首页
        url = "https://www.cuhk.edu.cn/zh-hans"
        result = self.crawler.crawl_page(url)
        
        # 获取元数据
        metadata = result["metadata"]
        
        # 打印元数据，帮助调试
        print("\n提取的元数据字段:")
        for key in metadata.keys():
            print(f"  - {key}")
        
        # 验证标题被提取
        self.assertIn("title", metadata)
        self.assertTrue(len(metadata["title"]) > 0, "提取的标题为空")
        
        # 验证至少提取了一些元数据字段
        expected_fields = ["title", "headings", "h1_headings", "h2_headings", "related_links"]
        found_fields = 0
        for field in expected_fields:
            if field in metadata:
                found_fields += 1
        
        self.assertGreater(found_fields, 1, "提取的元数据字段太少")


if __name__ == "__main__":
    unittest.main() 