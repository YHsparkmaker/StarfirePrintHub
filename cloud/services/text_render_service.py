"""
星火智造云打印 — Markdown / LaTeX 文本 → PDF 渲染服务

管线:
  原始 Markdown 文本
    → 提取 LaTeX 数学公式 → MathML 替换
    → markdown → HTML (pymdown-extensions)
    → 包裹 CSS 样式模板
    → weasyprint → PDF
    → 保存到 uploads/ 返回路径
"""

import logging
import re
import uuid
from pathlib import Path
from typing import Optional

import markdown
from latex2mathml.converter import convert as latex_to_mathml

from config import settings

logger = logging.getLogger(__name__)

# ── LaTeX 正则: 块级 $$...$$ 和行内 $...$ ──
_LATEX_BLOCK_RE = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL)
_LATEX_INLINE_RE = re.compile(r"(?<!\\)\$(.+?)(?<!\\)\$")


# ═══════════════════════════════════════════════════════════════════
# HTML 渲染模板
# ═══════════════════════════════════════════════════════════════════

def _build_html(media: str) -> str:
    """构建 HTML 模板, 纸张尺寸由 media 决定"""
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
  }}
  h1 {{ font-size: 1.8em; border-bottom: 2px solid #39ff14; padding-bottom: 6px; margin-top: 0.8em; }}
  h2 {{ font-size: 1.4em; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 0.8em; }}
  h3 {{ font-size: 1.2em; }}
  code {{
    font-family: "Courier New", monospace;
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.92em;
  }}
  pre {{
    background: #1e1e2e;
    color: #cdd6f4;
    padding: 14px 18px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 10pt;
    line-height: 1.5;
  }}
  pre code {{ background: none; padding: 0; color: inherit; }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
  }}
  th, td {{
    border: 1px solid #ccc;
    padding: 8px 12px;
    text-align: left;
  }}
  th {{ background: #e8e8e8; }}
  blockquote {{
    border-left: 3px solid #ccc;
    margin: 1em 0;
    padding: 4px 16px;
    color: #555;
    background: #f9f9f9;
  }}
  math[display="block"] {{
    display: block;
    margin: 16px 0;
    overflow-x: auto;
  }}
  ul, ol {{ padding-left: 1.5em; }}
  img {{ max-width: 100%; }}
</style>
</head>
<body>
{{body}}
</body>
</html>"""


class TextRenderService:
    """Markdown + LaTeX → PDF 渲染器"""

    # ═══════════════════════════════════════════════════════════════
    # 公开方法: 渲染并保存
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def render_to_pdf(
        markdown_text: str,
        filename_prefix: str = "text",
        header_info: Optional[dict] = None,
        media: str = "A4",
    ) -> Path:
        """
        将 Markdown 文本渲染为 PDF 并保存

        Args:
            markdown_text: 原始 Markdown + LaTeX 文本
            filename_prefix: 文件名前缀
            header_info: 页首使用信息 {subject, class_name, school_label}
            media: 目标纸张尺寸 (A4/A3/8K/Letter 等)

        Returns:
            生成的 PDF 文件路径
        """
        # 0. 构建页首信息 HTML
        header_html = ""
        if header_info:
            parts = []
            if header_info.get("subject"):
                parts.append(f'<span>科目: {header_info["subject"]}</span>')
            if header_info.get("class_name"):
                parts.append(f'<span>班级: {header_info["class_name"]}</span>')
            if header_info.get("school_label"):
                parts.append(f'<span>校标: {header_info["school_label"]}</span>')
            if parts:
                header_html = (
                    '<div style="border-bottom: 3px double #39ff14; '
                    'padding-bottom: 10px; margin-bottom: 18px; '
                    'display: flex; gap: 28px; font-size: 11pt; color: #444;">'
                    + "".join(parts)
                    + "</div>"
                )

        # 1. LaTeX → MathML 预处理
        html_body = TextRenderService._latex_preprocess(markdown_text)

        # 2. Markdown → HTML
        html_body = markdown.markdown(
            html_body,
            extensions=[
                "pymdownx.extra",          # tables / fenced_code / etc
                "pymdownx.highlight",       # syntax highlighting
                "pymdownx.superfences",     # nested code fences
                "pymdownx.tasklist",        # checkboxes
                "nl2br",                   # newline → <br>
            ],
            extension_configs={
                "pymdownx.highlight": {
                    "linenums": False,
                    "guess_lang": True,
                },
            },
        )

        # 3. 包裹完整 HTML (纸张尺寸由 media 决定)
        # 用 replace 而非 format, 避免用户内容中的 { } 被误解析
        full_html = _build_html(media).replace("{body}", header_html + html_body)

        # 4. HTML → PDF 并保存
        output_dir = settings.UPLOAD_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{filename_prefix}_{uuid.uuid4().hex[:12]}.pdf"
        pdf_path = output_dir / safe_name

        from weasyprint import HTML
        HTML(string=full_html).write_pdf(str(pdf_path))

        logger.info(f"文本 PDF 已生成: {pdf_path}")
        return pdf_path

    # ═══════════════════════════════════════════════════════════════
    # LaTeX → MathML 预处理
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _latex_preprocess(raw: str) -> str:
        """
        扫描文本中的 LaTeX 公式并转为 MathML。

        规则:
          $$...$$  → <math display="block">...</math>
          $...$    → <math display="inline">...</math>
        """

        # ── 块级公式 $$...$$ ──
        def _replace_block(m: re.Match) -> str:
            try:
                mathml = latex_to_mathml(m.group(1).strip())
                return f'<math display="block" xmlns="http://www.w3.org/1998/Math/MathML">{mathml}</math>'
            except Exception:
                logger.warning(f"LaTeX 块级转换失败: {m.group(1)[:60]}")
                return f"<pre>{m.group(0)}</pre>"

        raw = _LATEX_BLOCK_RE.sub(_replace_block, raw)

        # ── 行内公式 $...$ ──
        def _replace_inline(m: re.Match) -> str:
            try:
                mathml = latex_to_mathml(m.group(1).strip())
                return f'<math xmlns="http://www.w3.org/1998/Math/MathML">{mathml}</math>'
            except Exception:
                logger.warning(f"LaTeX 行内转换失败: {m.group(1)[:60]}")
                return f"<code>{m.group(0)}</code>"

        raw = _LATEX_INLINE_RE.sub(_replace_inline, raw)

        return raw
