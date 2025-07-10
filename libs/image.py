# 标准库
import os
import tempfile
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

# 第三方库
import imgkit
from bs4 import BeautifulSoup






def fix_image_links(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(src=True):
        tag["src"] = urljoin(base_url, tag["src"])
    for tag in soup.find_all("link", href=True):
        tag["href"] = urljoin(base_url, tag["href"])
    for tag in soup.find_all("script", src=True):
        tag["src"] = urljoin(base_url, tag["src"])
    return str(soup)




async def save_html_as_image(htmltext: str, filename_prefix: str):
    # wkhtmltoimage 路径（根据系统设置）
    if os.name == "nt":
        wkhtmltoimage_path = r"D:\Tool Software\wkhtmltopdf\bin\wkhtmltoimage.exe"
        wkhtml_config = imgkit.config(wkhtmltoimage=wkhtmltoimage_path)
    else:
        wkhtml_config = None

    # 写入临时 HTML 文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")    
    html_file = Path(f"temp_file/{filename_prefix}_{timestamp}.html")
    img_file = Path(f"temp_file/{filename_prefix}_{timestamp}.png")
    html_file.parent.mkdir(parents=True, exist_ok=True)    
    with html_file.open("w", encoding="utf-8") as f:
        f.write(htmltext)


    options = {
        'encoding': "UTF-8",
        'format': 'png',
        #'width': 800,
        'enable-local-file-access': '',
        'quiet': ''
    }

    imgkit.from_file(str(html_file), str(img_file), options=options, config=wkhtml_config)
    Path(html_file).unlink()    
    return img_file