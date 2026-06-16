"""
星火智造云打印 — 打印预览服务
将 PDF 按 CUPS 打印参数渲染为预览版本:
  - 按目标纸张尺寸生成画布 (A3 / A4 / Letter etc.)
  - n-up 拼版 (2-up / 4-up / 6-up / 9-up / 16-up)
  - 份数重复、双面标注、横向/竖向
"""

import io
import logging
from typing import Optional

from pypdf import PdfReader, PdfWriter, PageObject, Transformation

logger = logging.getLogger(__name__)

# ── 纸张尺寸 (pt, 1pt = 1/72 inch) ──
PAPER_SIZES_PT = {
    "A4":     (595,  842),
    "A3":     (842, 1191),
    "A5":     (420,  595),
    "Letter": (612,  792),
    "Legal":  (612, 1008),
    "B5":     (516,  729),
}

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
    media: str = "A4",
    number_up: int = 1,
    sides: str = "one-sided",
    copies: int = 1,
    orientation: str = "portrait",
    header_info: Optional[dict] = None,
) -> bytes:
    """
    对 PDF 应用打印参数, 返回预览 PDF 字节

    Args:
        pdf_bytes:   原始 PDF 文件内容
        media:       纸张尺寸 (A4/A3/Letter etc.)
        number_up:   n-up 拼版 (1/2/4/6/9/16)
        sides:       双面模式 (one-sided / two-sided-long-edge)
        copies:      份数
        orientation: 打印方向 (portrait / landscape)

    Returns:
        处理后的 PDF 字节
    """
    if not pdf_bytes:
        return b""

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    if total_pages == 0:
        return b""

    # ── 目标纸张尺寸 ──
    paper_w, paper_h = PAPER_SIZES_PT.get(media, PAPER_SIZES_PT["A4"])
    if orientation == "landscape":
        paper_w, paper_h = paper_h, paper_w

    number_up = number_up if number_up in _GRID else 1
    cols, rows = _GRID[number_up]
    per_sheet = cols * rows

    # ── 1. 构建页面列表 (含份数) ──
    page_list = list(reader.pages) * max(copies, 1)

    # ── 2. 横向: 页面旋转90°, 让内容填充 landscape cell ──
    if orientation == "landscape":
        page_list = [_rotate_landscape(p) for p in page_list]

    # ── 3. 拼版 ──
    writer = PdfWriter()
    if per_sheet == 1:
        for page in page_list:
            fitted = _fit_page_to_paper(page, paper_w, paper_h)
            writer.add_page(fitted)
    else:
        chunks = [page_list[i:i + per_sheet] for i in range(0, len(page_list), per_sheet)]
        for chunk in chunks:
            while len(chunk) < per_sheet:
                chunk.append(PageObject.create_blank_page(width=paper_w, height=paper_h))
            sheet = _make_nup_sheet(chunk, cols, rows, paper_w, paper_h)
            writer.add_page(sheet)

    # ── 4. 页首信息标注 ──
    if header_info:
        writer = _annotate_header(writer, paper_w, paper_h, header_info)

    # ── 5. 双面标注 ──
    if sides != "one-sided":
        writer = _annotate_duplex_label(writer)

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════
# 单页适应纸张 (居中缩放)
# ═══════════════════════════════════════════════════════════════════

def _fit_page_to_paper(page: PageObject, paper_w: float, paper_h: float) -> PageObject:
    """将页面居中缩放到目标纸张"""
    pw = float(page.mediabox.width)
    ph = float(page.mediabox.height)

    if abs(pw - paper_w) < 1 and abs(ph - paper_h) < 1:
        return page  # 尺寸已匹配, 无需变换

    scale = min(paper_w / pw, paper_h / ph)
    scaled_w = pw * scale
    scaled_h = ph * scale
    tx = (paper_w - scaled_w) / 2
    ty = (paper_h - scaled_h) / 2

    sheet = PageObject.create_blank_page(width=paper_w, height=paper_h)
    sheet.merge_transformed_page(
        page,
        Transformation().scale(scale).translate(tx / scale, ty / scale),
    )
    return sheet


# ═══════════════════════════════════════════════════════════════════
# 横向旋转
# ═══════════════════════════════════════════════════════════════════

def _rotate_landscape(page: PageObject) -> PageObject:
    """将页面旋转 90° 以模拟横向打印内容"""
    page.rotate(90)
    return page


# ═══════════════════════════════════════════════════════════════════
# n-up 拼版
# ═══════════════════════════════════════════════════════════════════

def _make_nup_sheet(
    pages: list,
    cols: int,
    rows: int,
    paper_w: float,
    paper_h: float,
) -> PageObject:
    """将多页拼合到一张目标纸张上 (网格布局, 居中缩放)"""
    cell_w = paper_w / cols
    cell_h = paper_h / rows

    sheet = PageObject.create_blank_page(width=paper_w, height=paper_h)

    for idx, page in enumerate(pages):
        col = idx % cols
        row = idx // cols

        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)

        # 缩放比例: 填满 cell 且不溢出
        scale = min(cell_w / pw, cell_h / ph)

        scaled_w = pw * scale
        scaled_h = ph * scale

        # cell 左上角 + 居中偏移
        cell_x = col * cell_w
        cell_y = paper_h - (row + 1) * cell_h

        tx = cell_x + (cell_w - scaled_w) / 2
        ty = cell_y + (cell_h - scaled_h) / 2

        sheet.merge_transformed_page(
            page,
            Transformation().scale(scale).translate(tx / scale, ty / scale),
        )

    return sheet


# ═══════════════════════════════════════════════════════════════════
# 页首使用信息标注
# ═══════════════════════════════════════════════════════════════════

def _annotate_header(
    writer: PdfWriter,
    paper_w: float,
    paper_h: float,
    header_info: dict,
) -> PdfWriter:
    """在首页顶部添加使用信息标注"""
    parts = []
    if header_info.get("subject"):
        parts.append(f"科目: {header_info['subject']}")
    if header_info.get("class_name"):
        parts.append(f"班级: {header_info['class_name']}")
    if header_info.get("school_label"):
        parts.append(f"{header_info['school_label']}")
    if not parts:
        return writer

    text = "  |  ".join(parts)
    writer.add_annotation(
        page_number=0,
        annotation={
            "/Type": "/Annot",
            "/Subtype": "/FreeText",
            "/Contents": text,
            "/DA": "/Helv 10 Tf 0.2 0.7 0.2 rg",
            "/Rect": [10, paper_h - 30, paper_w - 10, paper_h - 8],
            "/F": 4,
        },
    )
    return writer


# ═══════════════════════════════════════════════════════════════════
# 双面标注
# ═══════════════════════════════════════════════════════════════════

def _annotate_duplex_label(writer: PdfWriter) -> PdfWriter:
    """在每页右上角标 FRONT / BACK"""
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
                "/F": 4,
            },
        )
    return writer
