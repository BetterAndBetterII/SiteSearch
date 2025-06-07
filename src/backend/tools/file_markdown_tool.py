import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import base64
from pdf2image import convert_from_path
from markitdown import MarkItDown
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor
import tempfile

def doc_to_pdf(input_path: str, output_dir: str = None) -> str:
    """
    将文档(docx, pptx等)转换为PDF

    Args:
        input_path: 输入文件路径
        output_dir: 输出目录（可选）

    Returns:
        输出PDF文件路径
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"找不到输入文件: {input_path}")

        # 处理输出路径
        input_file = Path(input_path)
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = input_file.parent

        # 生成临时文件名
        output_pdf = output_path / f"{input_file.stem}.pdf"

        # 使用 LibreOffice 进行转换
        cmd = [
            'soffice',
            '--headless',
            '--convert-to',
            'pdf',
            '--outdir',
            str(output_path),
            str(input_file)
        ]
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            raise Exception(f"LibreOffice 转换失败: {process.stderr}")
            
        print(f"转换成功！PDF已保存到: {output_pdf}")
        return str(output_pdf)
        
    except Exception as e:
        print(f"转换失败: {str(e)}")
        return ""

def split_image(image, max_height=4000, max_width=4000):
    """
    将大图片切分成多个较小的图片

    Args:
        image: PIL Image对象
        max_height: 最大高度
        max_width: 最大宽度

    Returns:
        切分后的图片列表
    """
    width, height = image.size
    split_images = []
    
    # 如果图片尺寸在限制范围内，直接返回
    if width <= max_width and height <= max_height:
        return [image]
    
    # 根据宽高比决定切分方向
    if height > max_height:
        # 垂直切分
        num_splits = (height + max_height - 1) // max_height
        for i in range(num_splits):
            top = i * max_height
            bottom = min((i + 1) * max_height, height)
            split_images.append(image.crop((0, top, width, bottom)))
    elif width > max_width:
        # 水平切分
        num_splits = (width + max_width - 1) // max_width
        for i in range(num_splits):
            left = i * max_width
            right = min((i + 1) * max_width, width)
            split_images.append(image.crop((left, 0, right, height)))
            
    return split_images

def pdf_to_image(input_path: str, output_dir: str = None) -> str:
    """
    将PDF文件转换为图片

    Args:
        input_path: PDF文件路径
        output_dir: 输出目录（可选）

    Returns:
        输出目录路径
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"找不到输入文件: {input_path}")

        # 处理输出路径
        input_file = Path(input_path)
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = input_file.parent / f"{input_file.stem}_images"
            output_path.mkdir(parents=True, exist_ok=True)

        # 转换PDF为图片
        try:
            images = convert_from_path(input_path)
            if not images:
                raise Exception("PDF文件未能转换为图片（可能是空PDF或格式错误）")
        except Exception as e:
            print(f"PDF转图片失败: {str(e)}")
            raise Exception(f"PDF转图片失败: {str(e)}")
        
        # 保存图片
        page_count = 1
        for i, image in enumerate(images):
            # 切分大图片
            split_images = split_image(image)
            
            # 保存切分后的图片
            for j, split_img in enumerate(split_images):
                if len(split_images) == 1:
                    image_path = output_path / f"page_{page_count}.png"
                else:
                    image_path = output_path / f"page_{page_count}_{j+1}.png"
                split_img.save(str(image_path), "PNG")
            page_count += 1
            
        print(f"转换成功！图片已保存到: {output_path}")
        return str(output_path)
        
    except Exception as e:
        print(f"转换失败: PDF转图片错误 - {str(e)}")
        return ""

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def image_to_markdown(input_dir: str, output_file: str, workers: int = 30) -> str:
    """
    将图片转换为Markdown格式
    
    Args:
        input_path: 输入图片所在目录
        output_file: 输出文件位置
    
    Returns:
        输出文件路径
    """
    try:
        # 处理输出路径
        input_dir = Path(input_dir)
        output_file = Path(output_file)
        
        # 确保输出目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化OpenAI客户端
        client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),  # 从环境变量获取base_url
            max_retries=5,  # 减少重试次数以避免过长等待
        )
        
        # 获取目录下所有PNG图片并按名称排序
        image_files = sorted(
            [f for f in input_dir.glob("*.png")],
            key=lambda x: int(x.stem.split('_')[1]) if '_' in x.stem else int(x.stem)
        )
        
        if not image_files:
            raise Exception("未找到PNG图片文件")
            
        # 存储所有页面的markdown内容
        all_markdown = {k: None for k in range(len(image_files))}
        processed_count = 0  # 成功处理的图片数量

        def _process_image(image_file, index):
            print(f"正在处理图片: {image_file.name}")
            
            # 将图片转换为base64
            base64_image = encode_image_to_base64(str(image_file))
            
            # 调用OpenAI API
            response = client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please convert the content of this image to markdown format. Maintain the original formatting and structure, including headings, lists, tables, etc. Only return the markdown content without any additional explanation."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ]
            )
            
            # 获取转换结果
            markdown_content = response.choices[0].message.content
            if markdown_content.startswith('```markdown'):
                markdown_content = markdown_content[11:]
                markdown_content = markdown_content.replace('```', '')
            all_markdown[index] = markdown_content
        
        # 线程池处理每张图片
        with ThreadPoolExecutor(max_workers=min(workers, len(image_files))) as executor:
            executor.map(_process_image, image_files, range(len(image_files)))

        # 将所有内容写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join([v for v in all_markdown.values() if v is not None]))
            
        print(f"转换成功！Markdown文件已保存到: {output_file}")
        return str(output_file)
        
    except Exception as e:
        print(f"转换失败: {str(e)}")
        return ""

def markitdown_converter(input_path: str, output_dir: str = None) -> str:
    """
    将文档转换为Markdown格式
    
    Args:
        input_path: 输入文件路径
        output_dir: 输出目录（可选）
    
    Returns:
        转换后的文件路径
    """
    try:
        
        # 检查输入文件是否存在
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"找不到输入文件: {input_path}")
        # 处理输出路径
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = input_path.parent
            
        # 生成输出文件名
        output_file = output_path / f"{input_path.stem}.md"
        
        # 初始化转换器
        md = MarkItDown()
        # 转换文档
        result = md.convert(str(input_path))
        # 保存转换结果
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.text_content)
            
        print(f"转换成功！文件已保存到: {output_file}")
        return str(output_file)
        
    except Exception as e:
        print(f"转换失败: {str(e)}")
        return ""

def ai_converter(input_path: str, output_dir: str = None, manual_type: str = None) -> str:
    """
    通过文档->PDF->图片->Markdown的转换链实现文档到Markdown的转换
    如果输入文件已经是PDF，则跳过文档转PDF步骤
    如果输入文件是图片，则直接进行图片转Markdown步骤
    
    Args:
        input_path: 输入文件路径
        output_dir: 输出目录（可选）
        manual_type: 手动指定文件类型，可选值为：pdf, docx, pptx, png, jpg, jpeg

    Returns:
        转换后的Markdown文件路径
    """
    workers = int(os.getenv('AI_CONVERTER_WORKERS', 10))
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_path):
            print(f"文件不存在: {input_path}")
            return ""
            
        # 创建临时目录
        input_file = Path(input_path)
        temp_dir = tempfile.mkdtemp()
        
        # 处理输出路径
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = input_file.parent
        output_file = output_path / f"{input_file.stem}.md"

        # 获取文件后缀（转换为小写进行比较）
        file_suffix = input_file.suffix.lower()
        
        # 判断输入文件类型
        if file_suffix in ['.png', '.jpg', '.jpeg'] or manual_type in ['png', 'jpg', 'jpeg']:
            # 如果是图片文件，创建临时图片目录并复制图片
            image_dir = Path(temp_dir)
            # 复制图片到临时目录
            import shutil
            image_path = image_dir / f"page_1{file_suffix}"
            shutil.copy2(input_path, image_path)
            # 转换为Markdown
            markdown_path = image_to_markdown(str(image_dir), str(output_file), workers)
        else:
            # 对于PDF和其他文档类型的处理
            if file_suffix == '.pdf' or manual_type == 'pdf':
                pdf_path = input_path
            else:
                # 步骤1: 转换为PDF
                pdf_path = doc_to_pdf(input_path, str(temp_dir))
                if not pdf_path or not os.path.exists(pdf_path):
                    print("文档转PDF失败")
                    # 清理临时文件
                    import shutil
                    shutil.rmtree(temp_dir)
                    return ""
                    
            # 步骤2: PDF转图片
            images_dir = pdf_to_image(pdf_path, str(temp_dir))
            if not images_dir or not os.path.exists(images_dir):
                print("PDF转图片失败")
                # 清理临时文件
                import shutil
                shutil.rmtree(temp_dir)
                return ""
                
            # 检查图片目录是否包含图片文件
            image_files = list(Path(images_dir).glob("*.png"))
            if not image_files:
                print(f"未在{images_dir}目录找到任何PNG图片")
                # 清理临时文件
                import shutil
                shutil.rmtree(temp_dir)
                return ""
                
            # 步骤3: 图片转Markdown
            markdown_path = image_to_markdown(images_dir, str(output_file), workers)
            
        if not markdown_path or not os.path.exists(markdown_path):
            print("转换Markdown失败")
            # 清理临时文件
            import shutil
            shutil.rmtree(temp_dir)
            return ""
            
        # 清理临时文件
        import shutil
        shutil.rmtree(temp_dir)
        
        return markdown_path
        
    except Exception as e:
        print(f"转换失败: {str(e)}")
        try:
            # 尝试清理临时文件
            import shutil
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        return ""

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='文档转Markdown转换工具')
    parser.add_argument('input', help='输入文件路径')
    parser.add_argument('-o', '--output', help='输出目录（可选）', default=None)
    parser.add_argument('-ai', '--use_ai', help='通过AI处理文档', action='store_true')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    if args.use_ai:
        ai_converter(args.input, args.output)
    else:
        markitdown_converter(args.input, args.output)

if __name__ == "__main__":
    # main()
    pdf_path = r"C:\Users\bette\AppData\Roaming\JetBrains\PyCharm2024.3\scratches\Study Scheme - ECE_2024-25 and thereafter_Circular (AB2024_C036)_0.pdf"
    ai_converter(pdf_path)
