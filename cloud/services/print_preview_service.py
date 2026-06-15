"""
星火智造云打印 — 打印预览服务
将 PDF 按 CUPS 打印参数渲染为预览版本:
  - n-up 拼版 (2-up / 4-up / 6-up / 9-up / 16-up)
  - 份数重复、双面标注
"""

import io
import logging

from pypdf import PdfReader, PdfWriter, PageObject, Transformation, PaperSize

logger = logging.getLogger(__name__)

# ── 网格配置: number_up → (cols, rows) ──
_GRID = {
    1:  (1, 1),
    2:  (2, 1),
    4:  (2, 2),
    6:  (3, 2),
    9:  (3, 3),
    16: (4, 4),
}


def generate_preview_pdf(
    pdf_bytes: bytes,
    number_up: int = 1,
    sides: str = "one-sided",
    copies: int = 1,
) -> bytes:
    """
    对 PDF 应用打印参数, 返回预览 PDF 字节

    Args:
        pdf_bytes: 原始 PDF 文件内容
        number_up: n-up 拼版 (1/2/4/6/9/16)
        sides: 双面模式 (one-sided / two-sided-long-edge)
        copies: 份数

    Returns:
        处理后的 PDF 字节
    """
    if not pdf_bytes:
        return b""

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    total_pages = len(reader.pages)

    if total_pages == 0:
        return b""

    number_up = number_up if number_up in _GRID else 1
    cols, rows = _GRID[number_up]
    per_sheet = cols * rows

    # ── 1. 构建页面列表 (含份数) ──
    page_list = []
    for _ in range(max(copies, 1)):
        for p in reader.pages:
            page_list.append(p)

    # ── 2. 拼版 ──
    if per_sheet == 1:
        for page in page_list:
            writer.add_page(page)
    else:
        chunks = [page_list[i:i + per_sheet] for i in range(0, len(page_list), per_sheet)]
        base_w = float(page_list[0].mediabox.width)
        base_h = float(page_list[0].mediabox.height)

        for chunk in chunks:
            # 补空白页到满格
            while len(chunk) < per_sheet:
                blank = PageObject.create_blank_page(width=base_w, height=base_h)
                chunk.append(blank)

            sheet = _make_nup_sheet(chunk, cols, rows, base_w, base_h)
            writer.add_page(sheet)

    # ── 3. 双面标注 ──
    if sides != "one-sided":
        writer = _annotate_duplex_label(writer)

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════
# n-up 拼版
# ═══════════════════════════════════════════════════════════════════

def _make_nup_sheet(
    pages: list,
    cols: int,
    rows: int,
    base_w: float,
    base_h: float,
) -> PageObject:
    """将多页拼合到一页上 (网格布局, 居中缩放)"""
    cell_w = base_w / cols
    cell_h = base_h / rows

    sheet = PageObject.create_blank_page(width=base_w, height=base_h)

    for idx, page in enumerate(pages):
        col = idx % cols
        row = idx // cols

        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        scale = min(cell_w / pw, cell_h / ph)

        scaled_w = pw * scale
        scaled_h = ph * scale
        offset_x = col * cell_w + (cell_w - scaled_w) / 2
        offset_y = base_h - (row + 1) * cell_h + (cell_h - scaled_h) / 2

        sheet.merge_transformed_page(
            page,
            Transformation().scale(scale).translate(offset_x / scale, offset_y / scale),
        )

    return sheet


# ═══════════════════════════════════════════════════════════════════
# 双面标注
# ═══════════════════════════════════════════════════════════════════

def _annotate_duplex_label(writer: PdfWriter) -> PdfWriter:
    """在每页右上角标 FRONT / BACK (纯文本覆盖, 简单实现)"""
    # pypdf 原生不支持直接写文本; 这里使用 free_text annotation
    for i in range(len(writer.pages)):
        side = "FRONT" if i % 2 == 0 else "BACK"
        writer.add_annotation(
            page_number=i,
            annotation={
                "/Type": "/Annot",
                "/Subtype": "/FreeText",
                "/Contents": side,
                "/DA": "/Helv 10 Tf 0.8 0.4 0 rg",
                "/Rect": [480, 810, 595, 842],
                "/F": 4,  # Print
            },
        )
    return writer
