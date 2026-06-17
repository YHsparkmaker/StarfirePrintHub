"""
星火智造云打印 — 文档转换服务
将 DOCX / DOC / TXT / 图片 等非 PDF 文件转换为 PDF

转换策略:
  .docx  → python-docx 提取文本 → weasyprint 渲染 PDF
  .doc   → LibreOffice --headless (若可用) → PDF
           否则报错提示用户转为 .docx/.pdf 后上传
  .txt   → 直接 weasyprint 渲染
  .png/jpg → base64 嵌入 HTML → weasyprint 渲染 PDF
"""

import io
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# 需要转换的扩展名
CONVERTIBLE_EXTENSIONS = {".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg"}

# HTML 包裹模板 (纸张尺寸由 media 参数决定)
def _html_wrapper(media: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<style>
  @page {{ size: {media}; margin: 2cm 2.2cm; }}
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
<body>{{body}}</body>
</html>"""


def needs_conversion(filename: str) -> bool:
    """判断文件是否需要转换为 PDF"""
    ext = Path(filename).suffix.lower()
    return ext in CONVERTIBLE_EXTENSIONS


def extract_text_and_convert(file_bytes: bytes, filename: str, media: str = "A4") -> bytes:
    """
    从 DOCX/DOC/TXT/图片 提取内容并渲染为 PDF

    Args:
        file_bytes: 原始文件字节
        filename: 原始文件名 (用于判断类型)
        media: 目标纸张尺寸 (A4/A3/8K/Letter 等)

    Returns:
        PDF 字节内容
    """
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        text = file_bytes.decode("utf-8", errors="replace")
        return _html_to_pdf(text, media)

    elif ext == ".docx":
        text = _extract_docx(file_bytes)
        return _html_to_pdf(text, media)

    elif ext == ".doc":
        return _convert_doc_via_libreoffice(file_bytes, filename)

    elif ext in (".png", ".jpg", ".jpeg"):
        import base64
        b64 = base64.b64encode(file_bytes).decode()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}[ext.lstrip(".")]
        text = f'<img src="data:{mime};base64,{b64}" style="max-width:100%; height:auto;"/>'
        return _html_to_pdf(text, media)

    else:
        raise ValueError(f"不支持的文件类型: {ext}")


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
    elif ext == ".docx":
        return _extract_docx(file_bytes)
    elif ext == ".doc":
        # 旧版 Word: 尝试提取文本, 无排版
        return _extract_doc_text_fallback(file_bytes)
    elif ext in (".png", ".jpg", ".jpeg"):
        return ""
    return ""


# ═══════════════════════════════════════════════════════════════════
# DOCX 文本提取 (python-docx)
# ═══════════════════════════════════════════════════════════════════

def _extract_docx(file_bytes: bytes) -> str:
    """从 DOCX 提取纯文本"""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs) if paragraphs else "(文档内容为空)"
    except Exception as e:
        logger.warning(f"DOCX 解析失败: {e}")
        raise ValueError(
            "DOCX 文件无法解析, 文件可能已损坏。"
            "请尝试另存为新文件后重新上传。"
        ) from e


# ═══════════════════════════════════════════════════════════════════
# 旧版 DOC 转换 (LibreOffice headless)
# ═══════════════════════════════════════════════════════════════════

def _convert_doc_via_libreoffice(file_bytes: bytes, filename: str) -> bytes:
    """
    使用 LibreOffice headless 将 .doc 转换为 PDF

    如果 LibreOffice 不可用, 抛出明确错误提示用户升级文件格式。
    """
    libreoffice = shutil.which("libreoffice") or shutil.which("soffice")

    if not libreoffice:
        raise ValueError(
            "旧版 .doc 文件 (Word 97-2003) 不被 python-docx 支持。\n"
            "请在 Word 中将文件另存为 .docx 或 .pdf 格式后重新上传。\n\n"
            "服务器管理员: 安装 LibreOffice 可自动转换:\n"
            "  sudo apt install -y libreoffice-impress"
        )

    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp_in:
        tmp_in.write(file_bytes)
        doc_path = Path(tmp_in.name)

    tmp_dir = Path(tempfile.mkdtemp())

    try:
        result = subprocess.run(
            [
                libreoffice,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(tmp_dir),
                str(doc_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # LibreOffice 输出文件名 = 原文件名.pdf
        pdf_name = doc_path.stem + ".pdf"
        pdf_path = tmp_dir / pdf_name

        if not pdf_path.exists():
            # 有时 LibreOffice 加 .PDF 大写
            for f in tmp_dir.iterdir():
                if f.suffix.lower() == ".pdf":
                    pdf_path = f
                    break

        if not pdf_path.exists():
            logger.error(f"LibreOffice 转换失败: {result.stderr[:500]}")
            raise ValueError(
                f"LibreOffice 转换 {filename} 失败。"
                f"请将文件另存为 .docx 或 .pdf 后重新上传。"
            )

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        logger.info(f"LibreOffice 成功转换: {filename} → PDF ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    except subprocess.TimeoutExpired:
        raise ValueError(
            f"LibreOffice 转换 {filename} 超时。"
            f"文件可能包含复杂格式, 请另存为 .docx 或 .pdf 后上传。"
        )
    finally:
        try:
            doc_path.unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _extract_doc_text_fallback(file_bytes: bytes) -> str:
    """
    尝试从 .doc 提取纯文本 (用于在线编辑)

    优先级: antiword > catdoc > 手动二进制扫描
    """
    # 1. antiword (轻量, 离线)
    if shutil.which("antiword"):
        return _run_text_extractor("antiword", file_bytes, ".doc")

    # 2. catdoc
    if shutil.which("catdoc"):
        return _run_text_extractor("catdoc", file_bytes, ".doc", args=["-w"])

    # 3. LibreOffice 转 txt
    libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
    if libreoffice:
        return _run_text_extractor(libreoffice, file_bytes, ".doc",
                                   args=["--headless", "--convert-to", "txt:Text"])

    return ".doc 文件无法提取文本。请转换为 .docx 后上传以启用在线编辑。"


def _run_text_extractor(
    binary: str,
    file_bytes: bytes,
    suffix: str,
    args: list | None = None,
) -> str:
    """运行外部文本提取工具"""
    args = args or []
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(file_bytes)
        tmp_path = Path(f.name)

    try:
        result = subprocess.run(
            [binary] + args + [str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() if result.stdout else (
            result.stderr.strip() or "(未能提取文本内容)"
        )
    except Exception as e:
        logger.warning(f"{binary} 提取失败: {e}")
        return f"[文本提取失败: {binary} 不可用]"
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════
# HTML → PDF (weasyprint)
# ═══════════════════════════════════════════════════════════════════

def _html_to_pdf(html_body: str, media: str = "A4") -> bytes:
    """将 HTML 正文渲染为 PDF"""
    html = _html_wrapper(media).format(body=html_body)
    from weasyprint import HTML
    return HTML(string=html).write_pdf()
