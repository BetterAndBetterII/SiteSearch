"""
真实网站Firecrawl爬取测试模块
测试使用Firecrawl API对真实网站的抓取能力
"""

import os
import sys
import unittest
import time
from typing import Dict, Any
from unittest import mock
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.backend.sitesearch.crawler.firecrawl_worker import FirecrawlWorker


class TestFirecrawlWorker(unittest.TestCase):
    """Firecrawl爬虫真实网站测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 获取API密钥，如果环境变量中没有则跳过测试
        self.api_key = os.environ.get("FIRECRAWL_API_KEY")
        
        if not self.api_key:
            self.skipTest("未设置FIRECRAWL_API_KEY环境变量，跳过Firecrawl测试")
        
        # 定义测试的基础URL
        self.base_url = "https://www.cuhk.edu.cn"
        
        # 创建爬虫实例
        self.crawler = FirecrawlWorker(
            base_url=self.base_url,
            api_key=self.api_key,
            max_urls=5,
            max_depth=1,
            request_delay=1.0,
            timeout=60,  # Firecrawl API可能需要更长的超时时间
            formats=["markdown", "html"]  # 指定输出格式
        )
    
    def tearDown(self):
        """测试后的清理工作"""
        # 关闭爬虫
        if hasattr(self, 'crawler'):
            self.crawler.close()
    
    @mock.patch('firecrawl.firecrawl.FirecrawlApp.scrape_url')
    def test_homepage_crawl(self, mock_scrape_url):
        """测试爬取大学首页"""
        # 模拟API响应 - v2版本直接返回内容而不是job_id
        mock_scrape_url.return_value = {
            "markdown": "# 香港中文大学（深圳）\n\n香港中文大学（深圳）是一所经国家教育部批准的大学，特点是国际化的氛围、中英并重的教学环境。",
            "title": "香港中文大学（深圳）官网",
            "description": "香港中文大学（深圳）官方网站",
            "links": [
                "https://www.cuhk.edu.cn/zh-hans/about-us",
                "https://www.cuhk.edu.cn/zh-hans/news",
                "https://www.cuhk.edu.cn/zh-hans/academics"
            ]
        }
        
        # 爬取首页
        url = "https://www.cuhk.edu.cn/zh-hans"
        result = self.crawler.crawl_page(url)
        
        # 验证基本信息
        self.assertIsNotNone(result)
        self.assertEqual(result["url"], url)
        self.assertEqual(result["status_code"], 200)
        
        # 验证内容
        content = result["content"]
        print(f"\n获取到的内容: {content[:200]}...")  # 打印前200个字符用于调试
        
        expected_keywords = ["香港中文大学", "深圳"]
        for keyword in expected_keywords:
            self.assertIn(keyword, content, f"内容中未找到关键词: {keyword}")
        
        # 验证元数据
        self.assertIn("metadata", result)
        metadata = result["metadata"]
        self.assertIn("title", metadata)
        self.assertEqual(metadata["title"], "香港中文大学（深圳）官网")
        
        # 验证提取的链接
        self.assertIn("related_links", metadata)
        links = metadata["related_links"]
        self.assertEqual(len(links), 3)
        self.assertIn("https://www.cuhk.edu.cn/zh-hans/about-us", links)
    
    @mock.patch('firecrawl.firecrawl.FirecrawlApp.scrape_url')
    def test_about_us_page(self, mock_scrape_url):
        """测试爬取'关于我们'页面"""
        # 模拟API响应
        mock_scrape_url.return_value = {
            "markdown": "# 关于我们\n\n香港中文大学（深圳）是一所经国家教育部批准的大学，实行书院制教育。",
            "title": "关于我们 | 香港中文大学（深圳）",
            "description": "香港中文大学（深圳）简介",
            "links": ["https://www.cuhk.edu.cn/zh-hans/governing-board"]
        }
        
        # 爬取关于我们页面
        url = "https://www.cuhk.edu.cn/zh-hans/about-us"
        result = self.crawler.crawl_page(url)
        
        # 验证基本信息
        self.assertIsNotNone(result)
        self.assertEqual(result["url"], url)
        self.assertEqual(result["status_code"], 200)
        
        # 验证内容
        content = result["content"]
        expected_keywords = ["关于我们", "香港中文大学", "深圳"]
        for keyword in expected_keywords:
            self.assertIn(keyword, content, f"内容中未找到关键词: {keyword}")
        
        # 验证元数据
        metadata = result["metadata"]
        self.assertEqual(metadata["title"], "关于我们 | 香港中文大学（深圳）")
    
    @mock.patch('firecrawl.firecrawl.FirecrawlApp.crawl_url')
    @mock.patch('firecrawl.firecrawl.FirecrawlApp.check_crawl_status')
    def test_crawl_website(self, mock_check_crawl_status, mock_crawl_url):
        """测试爬取整个网站"""
        # 模拟API响应
        mock_crawl_url.return_value = {"job_id": "test-crawl-job-id"}
        
        # 模拟任务状态和结果
        mock_check_crawl_status.return_value = {
            "status": "completed", 
            "statistics": {"pages_crawled": 5, "pages_queued": 0},
            "result": {
                "pages": [
                    {
                        "url": "https://www.cuhk.edu.cn/zh-hans",
                        "markdown": "# 香港中文大学（深圳）\n\n主页内容",
                        "title": "首页 | 香港中文大学（深圳）",
                        "links": ["https://www.cuhk.edu.cn/zh-hans/about-us"]
                    },
                    {
                        "url": "https://www.cuhk.edu.cn/zh-hans/about-us",
                        "markdown": "# 关于我们\n\n关于页面内容",
                        "title": "关于我们 | 香港中文大学（深圳）",
                        "links": []
                    }
                ]
            }
        }
        
        # 执行爬取
        result = self.crawler.crawl()
        
        # 验证结果
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(self.crawler.crawled_urls), 2)  # 应该有2个页面被爬取
        
        # 验证结果中包含了期望的URL
        self.assertIn("https://www.cuhk.edu.cn/zh-hans", self.crawler.crawled_urls)
        self.assertIn("https://www.cuhk.edu.cn/zh-hans/about-us", self.crawler.crawled_urls)
        
        # 验证内容是否被保存
        self.assertIn("https://www.cuhk.edu.cn/zh-hans", self.crawler.results)
        saved_content = self.crawler.results["https://www.cuhk.edu.cn/zh-hans"]["content"]
        self.assertIn("香港中文大学", saved_content)
    
    @mock.patch('firecrawl.firecrawl.FirecrawlApp.scrape_url')
    def test_discover_sitemap(self, mock_scrape_url):
        """测试发现网站地图"""
        # 模拟API响应 - 首先返回robots.txt内容
        mock_scrape_url.side_effect = [
            # 第一次调用模拟robots.txt
            {
                "content": "User-agent: *\nDisallow: /private/\nSitemap: https://www.cuhk.edu.cn/sitemap.xml"
            },
            # 第二次调用模拟sitemap.xml
            {
                "content": """<?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                    <url><loc>https://www.cuhk.edu.cn/zh-hans</loc></url>
                    <url><loc>https://www.cuhk.edu.cn/zh-hans/about-us</loc></url>
                    <url><loc>https://www.cuhk.edu.cn/zh-hans/news</loc></url>
                </urlset>
                """
            }
        ]
        
        # 执行网站地图发现
        urls = self.crawler.discover_sitemap()
        
        # 验证结果
        self.assertEqual(len(urls), 3)
        self.assertIn("https://www.cuhk.edu.cn/zh-hans", urls)
        self.assertIn("https://www.cuhk.edu.cn/zh-hans/about-us", urls)
    
    def test_real_api_if_available(self):
        """如果有API密钥，尝试真实调用一次API"""
        if not self.api_key:
            self.skipTest("未设置FIRECRAWL_API_KEY环境变量，跳过真实API测试")
        
        try:
            # 尝试爬取一个真实页面
            url = "https://www.cuhk.edu.cn/zh-hans"
            result = self.crawler.crawl_page(url)
            
            # 简单验证返回结果
            self.assertIsNotNone(result)
            self.assertIn("url", result)
            self.assertIn("content", result)
            self.assertIn("metadata", result)
            
            # 打印一些信息用于验证
            print(f"\n真实API调用结果:")
            print(f"标题: {result['metadata'].get('title', '无标题')}")
            print(f"内容长度: {len(result['content'])} 字符")
            print(f"提取的链接数: {len(result['metadata'].get('related_links', []))}")
            
        except Exception as e:
            self.fail(f"真实API调用失败: {str(e)}")


# 仅当直接运行该模块时执行测试
if __name__ == "__main__":
    unittest.main() 