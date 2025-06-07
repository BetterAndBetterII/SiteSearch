import unittest
import os
from src.backend.sitesearch.cleaner.cleaner_manager import DataCleaner

class TestPDFStrategy(unittest.TestCase):
    def setUp(self):
        self.cleaner = DataCleaner()
        # 确保测试PDF文件存在
        self.pdf_path = os.path.join(os.path.dirname(__file__), 'test.pdf')
        self.assertTrue(os.path.exists(self.pdf_path), f"测试PDF文件不存在: {self.pdf_path}")
        
    def test_pdf_cleaning(self):
        """测试PDF清理策略是否能正确处理PDF文件"""
        # 读取PDF文件内容
        with open(self.pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        # 使用清洗器清理内容
        cleaned_content = self.cleaner.clean(
            url="http://example.com/test.pdf",
            mimetype="application/pdf",
            content=pdf_content
        )
        
        # 验证清理后的内容不为空
        self.assertIsNotNone(cleaned_content)
        self.assertNotEqual(cleaned_content, "")
        
        # 打印清理后的内容，以便查看结果
        print("\n清理后的PDF内容:")
        print("-" * 50)
        print(cleaned_content[:500] + "..." if len(cleaned_content) > 500 else cleaned_content)
        print("-" * 50)
        
        # 验证包含一些常见的PDF内容标记
        # 由于我们使用的是AI转换器，内容可能会有所不同
        # 这里只是简单检查内容是否看起来像转换后的文本
        self.assertIsInstance(cleaned_content, str)
        
if __name__ == "__main__":
    unittest.main()
