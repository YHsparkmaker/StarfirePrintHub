"""
星火智造云打印 — 文档转换服务
将 DOCX / TXT / DOC 等非 PDF 文件转换为 PDF
"""

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 需要转换的扩展名
CONVERTIBLE_EXTENSIONS = {".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg"}

# HTML 包裹模板
_HTML_WRAPPER = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<style>
  @page {{ size: A4; margin: 2cm 2.2cm; }}
  body {{
    font-family: "Noto Sans CJK SC", "Microsoft YaHei", "SimSun", sans-serif;
    font-size: 12pt;
    line-height: 1.8;
    color: #222;
    white-space: pre-wrap;
    word-wrap: break-word;
  }}
</style>
</head>
<body>{body}</body>
</html>"""


def needs_conversion(filename: str) -> bool:
    """判断文件是否需要转换为 PDF"""
    ext = Path(filename).suffix.lower()
    return ext in CONVERTIBLE_EXTENSIONS


def extract_text_and_convert(file_bytes: bytes, filename: str) -> bytes:
    """
    从 DOCX/TXT/图片 提取文本并渲染为 PDF

    Args:
        file_bytes: 原始文件字节
        filename: 原始文件名 (用于判断类型)

    Returns:
        PDF 字节内容
    """
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        text = file_bytes.decode("utf-8", errors="replace")
    elif ext in (".docx", ".doc"):
        text = _extract_docx_text(file_bytes, filename)
    elif ext in (".png", ".jpg", ".jpeg"):
        # 图片：包裹为 HTML 中的 <img> 再打印
        import base64
        b64 = base64.b64encode(file_bytes).decode()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext.lstrip("."), "image/png")
        text = f'<img src="data:{mime};base64,{b64}" style="max-width:100%; height:auto;"/>'
    else:
        raise ValueError(f"不支持的文件类型: {ext}")

    html = _HTML_WRAPPER.format(body=text)
    from weasyprint import HTML
    pdf_bytes = HTML(string=html).write_pdf()
    return pdf_bytes


def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    提取文件中的纯文本内容 (用于在线编辑)

    Args:
        file_bytes: 原始文件字节
        filename: 原始文件名

    Returns:
        提取的文本内容
    """
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        return file_bytes.decode("utf-8", errors="replace")
    elif ext in (".docx", ".doc"):
        return _extract_docx_text(file_bytes, filename)
    elif ext in (".png", ".jpg", ".jpeg"):
        return ""  # 图片无法提取文本
    return ""


def _extract_docx_text(file_bytes: bytes, filename: str) -> str:
    """从 DOCX 提取纯文本"""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.warning(f"DOCX 解析失败，尝试纯文本提取: {e}")
        # 回退: 如果是 .doc (旧格式), 可能解析失败
        # 返回原始文件名作为占位符
        return f"[无法解析 {filename}，请转换为 PDF 后上传]"
