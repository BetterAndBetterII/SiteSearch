import re
from bs4 import BeautifulSoup
from typing import List
import os

from src.backend.tools.markdown_tools import replace_base64, clean_md
from .base import DataCleaner
import html2text
import re
from urllib.parse import urlparse
import tempfile

from .base import CleaningStrategy

from src.backend.tools.file_markdown_tool import ai_converter, markitdown_converter


class SimpleHTMLCleaner(DataCleaner):
    """HTML清洗器，用于清理HTML内容，去除无用标签和空白"""
    
    # 需要移除的标签列表
    REMOVE_TAGS = [
        'script', 'style', 'meta', 'link', 'noscript', 
        'header', 'footer', 'nav', 'iframe'
    ]
    
    def __init__(self, remove_tags: List[str] = None):
        """初始化HTML清洗器
        
        Args:
            remove_tags: 需要移除的标签列表，如果不指定则使用默认列表
        """
        self.remove_tags = remove_tags or self.REMOVE_TAGS
    
    def clean(self, html: str) -> str:
        """清洗HTML内容
        
        Args:
            html: 原始HTML字符串
            
        Returns:
            清洗后的文本内容
        """
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html, 'lxml')
        
        # 移除不需要的标签
        for tag in self.remove_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 获取文本内容
        text = soup.get_text(separator='\n')
        
        # 清理文本
        lines = []
        for line in text.split('\n'):
            # 清理每一行
            line = line.strip()
            # 跳过空行
            if not line:
                continue
            # 清理连续的空白字符
            line = re.sub(r'\s+', ' ', line)
            lines.append(line)
        
        # 合并行，去除连续的重复行
        cleaned_lines = []
        prev_line = None
        for line in lines:
            # 跳过与前一行相同的内容
            if line == prev_line:
                continue
            cleaned_lines.append(line)
            prev_line = line
        
        # 合并所有行
        result = '\n'.join(cleaned_lines) 
        return replace_base64(result)
    
class IDExtractor(DataCleaner):
    # 需要提取的id列表
    EXTRACT_IDS = ['main']
    REMOVE_IDS = []

    def __init__(self, extract_ids: List[str] = None, remove_ids: List[str] = None):
        """初始化ID提取器"""
        self.extract_ids = extract_ids or self.EXTRACT_IDS
        self.remove_ids = remove_ids or self.REMOVE_IDS

    def clean(self, html: str) -> str:
        if not 'id="main"' in html:
            return html
        tree = BeautifulSoup(html, 'lxml')
        new_tree = BeautifulSoup()
        # 白名单，提取带有指定id的标签，其余标签移除
        for element in tree.find_all(id=self.extract_ids):
            new_tree.append(element)
        if self.remove_ids:
            # 黑名单，移除带有指定id的标签
            for element in new_tree.find_all(id=self.remove_ids):
                element.decompose()

        # 返回提取后的HTML
        return str(new_tree)

class MarkdownCleaner(DataCleaner):
    """HTML转Markdown清洗器，用于将HTML内容转换为Markdown格式"""
    
    def __init__(self, **kwargs):
        """初始化Markdown清洗器
        
        Args:
            **kwargs: 传递给html2text.HTML2Text的配置参数
        """
        self.h = html2text.HTML2Text()
        # 配置html2text
        self.h.body_width = 0  # 禁用自动换行
        self.h.unicode_snob = True  # 保留unicode字符
        self.h.ignore_links = False  # 保留链接
        self.h.ignore_images = False  # 保留图片
        self.h.ignore_emphasis = False  # 保留强调
        self.h.ignore_tables = False  # 保留表格
        # 更新用户自定义配置
        for key, value in kwargs.items():
            setattr(self.h, key, value)
    
    def clean(self, html: str) -> str:
        """将HTML转换为Markdown
        
        Args:
            html: 原始HTML字符串
            
        Returns:
            转换后的Markdown文本
        """
        markdown_text = self.h.handle(html).strip()
        markdown_text = replace_base64(markdown_text)
        markdown_text = clean_md(markdown_text)
        return markdown_text

class MarkdownTableCleaner(DataCleaner):
    """Markdown表格清洗器，用于清理Markdown表格"""

    def __init__(self):
        self.table_pattern = re.compile(r'\|.*\|')
        self.header_separator = re.compile(r'\|[\s\-:]+\|')
    
    def should_handle(self, content: str) -> bool:
        return '|' in content and self.table_pattern.search(content) is not None
    
    def clean(self, content_str: str) -> str:
        if not self.should_handle(content_str):
            return content_str
        lines = content_str.split('\n')
        result = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 检测是否为表格行
            if self.table_pattern.match(line):
                # 获取表头
                headers = [cell.strip() for cell in line.strip('|').split('|')]
                i += 1
                
                # 跳过分隔行
                if i < len(lines) and self.header_separator.match(lines[i].strip()):
                    i += 1
                
                # 处理数据行
                while i < len(lines) and self.table_pattern.match(lines[i].strip()):
                    cells = [cell.strip() for cell in lines[i].strip('|').split('|')]
                    # 展开每行数据，使用表头作为前缀
                    for header, cell in zip(headers, cells):
                        if cell and not cell.isspace():
                            result.append(f"{header}: {cell}")
                    result.append("")  # 添加空行分隔不同行的数据
                    i += 1
            else:
                result.append(line)
                i += 1
                
        return '\n'.join(result)

# ------------------------------------------------------------

class HTMLStrategy(CleaningStrategy):
    """HTML内容清洗策略"""
    
    def __init__(self):
        self.cleaner = SimpleHTMLCleaner()
    
    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        return mimetype.startswith('text/html')
    
    def clean(self, content: bytes | str) -> str:
        return self.cleaner.clean(content)

class MarkdownStrategy(CleaningStrategy):
    """将HTML转换为Markdown的策略"""
    
    def __init__(self):
        self.extractor = IDExtractor(['main'], ['block-cuhk-ui-breadcrumbs'])
        self.html_cleaner = SimpleHTMLCleaner()
        self.cleaner = MarkdownCleaner()
    
    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        return mimetype.startswith('text/html')

    def clean(self, content: bytes | str) -> str:
        extracted = self.extractor.clean(content)
        return self.cleaner.clean(extracted)

class SearchPageStrategy(CleaningStrategy):
    """教师、学生搜索页面"""

    def __init__(self):
        self.extractor = IDExtractor(['content'],
                                     [
                                         'views-exposed-form-course-search-page-teacher-search',
                                         'views-exposed-form-list-by-student-page-hide-student-search',
                                         'block-cuhk-ui-breadcrumbs',
                                     ])
        self.markdown_cleaner = MarkdownCleaner()

    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        if not mimetype.startswith('text/html'):
            return False
        domain = urlparse(url)
        valid_urls = [
            'teacher-search',
            'student-search',
            'PhDStudents'
        ]
        return any(url_part in domain.path for url_part in valid_urls) and 'id="content"' in content

    def clean(self, content: bytes | str) -> str:
        # 先提取文章主体
        extracted = self.extractor.clean(content)
        # 转换为Markdown
        return self.markdown_cleaner.clean(extracted)

class CommonPageStrategy(CleaningStrategy):
    """常见包含#main的page页面"""
    
    def __init__(self):
        self.extractor = IDExtractor(['main'], ['block-cuhk-ui-breadcrumbs'])
        self.markdown_cleaner = MarkdownCleaner()
    
    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        if not mimetype.startswith('text/html'):
            return False
        domain = urlparse(url)
        # contains page/
        return 'page/' in domain.path and 'id="main"' in content
    
    def clean(self, content: bytes | str) -> str:
        # 先提取文章主体
        extracted = self.extractor.clean(content)
        # 转换为Markdown
        return self.markdown_cleaner.clean(extracted)

class PlainTextStrategy(CleaningStrategy):
    """纯文本清洗策略"""
    
    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        return mimetype.startswith('text/plain')
    
    def clean(self, content: bytes | str) -> str:
        # 清理空白行和多余的空格
        lines = [re.sub(r'\s+', ' ', line.strip()) 
                for line in content.split('\n')]
        return '\n'.join(line for line in lines if line) 
    
class PDFStrategy(CleaningStrategy):
    """PDF内容清洗策略"""
    def __init__(self):
        self.markdown_table_cleaner = MarkdownTableCleaner()

    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        return mimetype.startswith('application/pdf')

    def clean(self, content: bytes | str) -> str:
        # 创建临时文件保存PDF内容
        temp_path = tempfile.mktemp()
        with open(temp_path, 'wb') as f:
            f.write(content)
            
        # 使用AI转换器处理PDF
        pdf_path = ai_converter(temp_path, manual_type='pdf')
        
        # 检查转换结果
        if not pdf_path or not os.path.exists(pdf_path):
            raise Exception("PDF转换失败，无法生成Markdown文件")
            
        # 读取转换后的文件内容
        with open(pdf_path, 'r', encoding="utf-8") as f:
            text = f.read()
            
        # 清理表格
        text = self.markdown_table_cleaner.clean(text)
        return text

class DocxStrategy(CleaningStrategy):
    """Docx内容清洗策略"""
    
    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        # application/vnd.openxmlformats-officedocument.wordprocessingml.document
        return mimetype.startswith('application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    def clean(self, content: bytes | str) -> str:
        try:
            # 创建临时文件保存Docx内容
            temp_path = tempfile.mktemp()
            with open(temp_path, 'wb') as f:
                f.write(content)
                
            # 使用AI转换器处理Docx
            docx_path = ai_converter(temp_path, manual_type='docx')
            
            # 检查转换结果
            if not docx_path or not os.path.exists(docx_path):
                print(f"Docx转换失败，无法生成Markdown文件")
                return "Docx文件转换失败，无法提取内容"
                
            # 读取转换后的文件内容
            with open(docx_path, 'r', encoding="utf-8") as f:
                text = f.read()
                
            return text
        except Exception as e:
            print(f"Docx处理错误: {str(e)}")
            return f"Docx处理失败: {str(e)}"
        
class MarkItDownStrategy(CleaningStrategy):
    """Excel内容清洗策略"""

    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        accept_mimetypes = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/xml'
        ]
        return any(mimetype.startswith(mimetype) for mimetype in accept_mimetypes)
    
    def clean(self, content: bytes | str) -> str:
        try:
            # 创建临时文件保存Excel内容
            temp_path = tempfile.mktemp()
            with open(temp_path, 'wb') as f:
                f.write(content)

            # 使用markitdown
            output_path = markitdown_converter(temp_path)
            with open(output_path, 'r', encoding="utf-8") as f:
                text = f.read()
            return text
        except Exception as e:
            print(f"Excel处理错误: {str(e)}")
            return f"Excel处理失败: {str(e)}"


class ImageDiscardStrategy(CleaningStrategy):
    """图片丢弃策略"""
    
    def should_handle(self, url: str, mimetype: str, content: str) -> bool:
        return mimetype.startswith('image/')
    
    def clean(self, content: bytes | str) -> str:
        return ""
