import re

base64_matches = ['data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/jpg;base64,']

def parse_links(md_content):
    links = []
    pattern = r'\[(.*?)\]\((.*?)\)'
    matches = re.finditer(pattern, md_content)
    for match in matches:
        links.append(match.group(2))
    return links

def replace_base64(md_content):
    links = parse_links(md_content)
    for link in links:
        for base64_match in base64_matches:
            if link.startswith(base64_match):
                md_content = md_content.replace(link, 'base64_image')
    return md_content

def clean_md(md_content):
    # 处理每一行
    lines = md_content.split('\n')
    cleaned_lines = []

    for line in lines:
        # 去除行首尾的空白字符
        line = line.strip()
        # 只保留非空行
        if line:
            # 将多个连续空格替换为单个空格
            line = ' '.join(line.split())
            # 去除包含base64_matches的行
            for base64_match in base64_matches:
                if base64_match in line:
                    line = ''
                    break
            cleaned_lines.append(line)
    
    # 重新组合文本，使用单个换行符连接
    cleaned_content = '\n'.join(cleaned_lines)
    return cleaned_content
