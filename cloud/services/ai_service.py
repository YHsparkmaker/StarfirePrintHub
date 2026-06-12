"""
星火智造云打印 — AI 摘要服务

功能流程:
  1. 接收 PDF 文件路径
  2. 使用 PyPDF2 提取 PDF 文本内容
  3. 调用 LLM (OpenAI 兼容接口) 生成中文摘要
  4. 将摘要渲染为一页 PDF
  5. 将该摘要页拼接到原 PDF 的最前面
  6. 返回摘要文本

注意:
  - AI 调用是异步的，不应阻塞上传接口的 HTTP 响应
  - 可在未来替换为 Amazon Bedrock / 本地模型 / 其他 LLM
"""

import io
import logging
from pathlib import Path
from typing import Optional

from PyPDF2 import PdfReader, PdfWriter
from pypdf import PdfReader as PyPdfReader

from config import settings

logger = logging.getLogger(__name__)


class AISummaryService:
    """
    AI 摘要服务
    ────────────
    封装了 PDF 文本提取 → LLM 摘要生成 → PDF 拼接的完整链路。
    """

    # ── LLM 提示词模板 ────────────────────────
    SUMMARY_PROMPT = """你是一个专业的文档摘要助手。请仔细阅读以下 PDF 文档内容，
用中文生成一份简洁的结构化摘要，包含以下部分：
1. 文档标题/主题
2. 核心要点 (3-5 条)
3. 适用场景或目标读者

文档内容：
{text}

请用 Markdown 格式输出摘要。"""

    @staticmethod
    def extract_text(pdf_path: str | Path) -> str:
        """
        从 PDF 中提取纯文本内容

        Args:
            pdf_path: PDF 文件路径

        Returns:
            提取出的文本 (最多 8000 字符，控制 token 用量)
        """
        logger.info(f"正在从 PDF 提取文本: {pdf_path}")
        reader = PdfReader(str(pdf_path))
        full_text_parts: list[str] = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text_parts.append(text)
                # 字符数上限保护 (约 2000 tokens)
                if sum(len(p) for p in full_text_parts) > 8000:
                    logger.warning(f"文本超过 8000 字符，在第 {i+1} 页截断")
                    break

        return "\n\n".join(full_text_parts)

    @staticmethod
    async def generate_summary(text: str) -> str:
        """
        调用 LLM 生成摘要

        Args:
            text: 待摘要的原文

        Returns:
            Markdown 格式的中文摘要
        """
        if not settings.AI_ENABLED or not settings.OPENAI_API_KEY:
            logger.warning("AI 未启用或缺少 API Key，返回占位摘要")
            return (
                "## 文档摘要\n\n"
                "> ⚠️ AI 摘要功能未启用\n\n"
                f"文档共 {len(text)} 字符, 请配置 OPENAI_API_KEY 后重试。"
            )

        try:
            # 延迟导入，避免未安装 openai 时启动崩溃
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )

            prompt = AISummaryService.SUMMARY_PROMPT.format(text=text)

            response = await client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的文档摘要助手，输出简洁有条理的中文摘要。"
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=600,
            )

            summary = response.choices[0].message.content or ""
            logger.info(f"AI 摘要生成成功, 长度: {len(summary)} 字符")
            return summary

        except Exception as e:
            logger.error(f"AI 摘要生成失败: {e}")
            return f"## 摘要生成失败\n\n错误信息: {str(e)}"

    @staticmethod
    def prepend_summary_page(
        pdf_path: str | Path,
        summary_text: str
    ) -> str:
        """
        【核心功能】将 AI 摘要页面拼接到原 PDF 的最前面

        实现原理:
          1. 使用 PyPDF2 读取原 PDF 所有页面
          2. 创建一个新 PDF 作为摘要封面页 (通过 reportlab 或纯文本写入)
          3. 将摘要页放在最前面，后面紧跟原 PDF 所有页面
          4. 写回原文件 (覆盖)

        Args:
            pdf_path: 原始 PDF 文件路径
            summary_text: AI 生成的摘要文本 (Markdown)

        Returns:
            拼接后的 PDF 文件路径 (与原路径相同)
        """
        import tempfile
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.enums import TA_LEFT, TA_CENTER

        logger.info(f"正在为 PDF 添加摘要封面: {pdf_path}")

        # ── Step 1: 创建摘要封面页 (临时 PDF) ──
        # 尝试注册中文字体，如果失败则使用默认字体
        try:
            # 常见的中文字体路径 (Linux / macOS)
            import platform
            system = platform.system()
            if system == "Darwin":
                font_path = "/System/Library/Fonts/PingFang.ttc"
            elif system == "Linux":
                font_path = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
            else:
                font_path = "C:/Windows/Fonts/msyh.ttc"  # 微软雅黑

            pdfmetrics.registerFont(TTFont("ChineseFont", font_path))
            _font_name = "ChineseFont"
        except Exception:
            logger.warning("无法加载中文字体，摘要将使用英文默认字体")
            _font_name = "Helvetica"

        # 创建临时摘要 PDF
        cover_path = Path(tempfile.mktemp(suffix=".pdf"))

        doc = SimpleDocTemplate(
            str(cover_path),
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()

        # 自定义样式
        title_style = ParagraphStyle(
            "SummaryTitle",
            parent=styles["Title"],
            fontName=_font_name,
            fontSize=22,
            leading=28,
            alignment=TA_CENTER,
            spaceAfter=12 * mm,
        )
        body_style = ParagraphStyle(
            "SummaryBody",
            parent=styles["Normal"],
            fontName=_font_name,
            fontSize=11,
            leading=18,
            alignment=TA_LEFT,
        )

        # 构建摘要内容流
        story = []

        # 标题
        story.append(Paragraph("📄 文档摘要", title_style))
        story.append(Spacer(1, 8 * mm))

        # 将 Markdown 摘要文本转为简单 HTML 段落
        for line in summary_text.strip().split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 4 * mm))
            elif line.startswith("## "):
                story.append(Paragraph(f"<b>{line[3:]}</b>", body_style))
            elif line.startswith("# "):
                story.append(Paragraph(f"<b>{line[2:]}</b>", title_style))
            elif line.startswith("- "):
                story.append(Paragraph(f"• {line[2:]}", body_style))
            elif line.startswith("> "):
                story.append(Paragraph(f"<i>{line[2:]}</i>", body_style))
            else:
                story.append(Paragraph(line, body_style))

        doc.build(story)

        # ── Step 2: 拼接摘要 PDF + 原 PDF ──
        original_reader = PdfReader(str(pdf_path))
        cover_reader = PdfReader(str(cover_path))
        writer = PdfWriter()

        # 先添加摘要封面页
        for page in cover_reader.pages:
            writer.add_page(page)

        # 再添加原始 PDF 全部页面
        for page in original_reader.pages:
            writer.add_page(page)

        # 写回原文件
        with open(pdf_path, "wb") as f:
            writer.write(f)

        # 清理临时文件
        cover_path.unlink(missing_ok=True)

        logger.info(f"PDF 摘要封面拼接完成: {pdf_path}")
        return str(pdf_path)


async def generate_ai_summary_and_prepend(
    pdf_path: str | Path,
    job_id: str
) -> Optional[str]:
    """
    【入口函数】异步生成 AI 摘要并拼接到 PDF 最前面

    这个函数设计为在后台异步执行，不阻塞上传接口的 HTTP 响应。
    调用方应在上传接口中通过 BackgroundTasks 或 asyncio.create_task 触发。

    Args:
        pdf_path: PDF 文件路径
        job_id: 任务 ID (用于日志追踪)

    Returns:
        生成的摘要文本，失败则返回 None
    """
    service = AISummaryService()

    try:
        logger.info(f"[Job {job_id}] 开始异步 AI 摘要生成...")

        # Step 1: 提取文本
        text = service.extract_text(pdf_path)
        if not text.strip():
            logger.warning(f"[Job {job_id}] PDF 无可提取文本")
            return None

        # Step 2: 调用 LLM
        summary = await service.generate_summary(text)
        if not summary:
            return None

        # Step 3: 拼接摘要到 PDF 最前面
        service.prepend_summary_page(pdf_path, summary)

        logger.info(f"[Job {job_id}] AI 摘要生成 & 拼接完成")
        return summary

    except Exception as e:
        logger.error(f"[Job {job_id}] AI 摘要流程异常: {e}")
        return None
