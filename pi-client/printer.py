"""
星火智造云打印 — CUPS 打印封装
负责:
  1. 将云端 JSON 参数映射为 CUPS 标准选项
  2. 检查打印机连接状态
  3. 提交打印作业到 CUPS 队列
"""

import logging
from pathlib import Path
from typing import Optional

import cups
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

from config import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 参数映射表: 云端 JSON key → CUPS 选项名 + 类型转换
# ═══════════════════════════════════════════════════════════════════

# 映射规则说明:
#   云端使用 JSON 风格的 key (如 number_up, sides)
#   CUPS 使用连字符风格的选项 (如 number-up, sides)
#   ➜ 映射表负责将两者对齐，同时做值的合法性校验

CUPS_OPTION_MAP = {
    # ── 份数 ──
    "copies": {
        "cups_key": "copies",
        "type": int,
        "default": 1,
        "validator": lambda v: 1 <= v <= 999,
    },
    # ── 双面打印 ──
    "sides": {
        "cups_key": "sides",
        "type": str,
        "default": "one-sided",
        "validator": lambda v: v in (
            "one-sided",
            "two-sided-long-edge",
            "two-sided-short-edge",
        ),
    },
    # ── 纸张尺寸 ──
    "media": {
        "cups_key": "media",
        "type": str,
        "default": "A4",
        "validator": lambda v: v in (
            "A4", "A3", "8K", "Letter", "Legal",
            "B4", "B5", "4x6", "5x7",
        ),
    },
    # ── 拼版 (每张纸放几页) ──
    "number_up": {
        "cups_key": "number-up",
        "type": int,
        "default": 1,
        "validator": lambda v: v in (1, 2, 4, 6, 9, 16),
    },
    # ── 打印方向 ──
    "orientation": {
        "cups_key": "orientation-requested",
        "type": str,
        "default": "portrait",
        "validator": lambda v: v in ("portrait", "landscape", "reverse-portrait", "reverse-landscape"),
    },
    # ── 纸盒来源 ──
    "media_source": {
        "cups_key": "media-source",
        "type": str,
        "default": "auto",
        "validator": lambda v: v in ("auto", "tray-1", "tray-2", "tray-3", "tray-4", "manual", "by-pass-tray"),
    },
    # ── 纸张类型 ──
    "media_type": {
        "cups_key": "media-type",
        "type": str,
        "default": "stationery",
        "validator": lambda v: v in (
            "stationery", "stationery-recycled", "stationery-lightweight",
            "stationery-heavyweight", "transparency", "labels",
            "envelope", "cardstock",
        ),
    },
    # ── 页面范围 ──
    "page_ranges": {
        "cups_key": "page-ranges",
        "type": str,
        "default": None,
        "validator": lambda v: v is None or bool(v.strip()),
    },
    # ── 打印质量 ──
    "print_quality": {
        "cups_key": "print-quality",
        "type": str,
        "default": "normal",
        "validator": lambda v: v in ("draft", "normal", "high"),
    },
    # ── 彩色/黑白 ──
    "color_mode": {
        "cups_key": "print-color-mode",
        "type": str,
        "default": "color",
        "validator": lambda v: v in ("color", "monochrome", "auto"),
    },
    # ── 自定义 CUPS 透传参数 ──
    "_raw_options": {
        "cups_key": None,  # 特殊处理: 直接 merge
        "type": dict,
        "default": {},
        "validator": lambda v: isinstance(v, dict),
    },
}

# ── 纸张尺寸映射 (名称 → 宽x高 mm) ──
# CUPS 对非标准/中文命名纸张 (8K, B4 等) 可能不识别，
# 必须转为 Custom.WIDTHxHEIGHTmm 格式才能被所有打印机接受。
PAPER_DIMENSIONS_MM: dict[str, tuple[int, int]] = {
    "A4":     (210, 297),
    "A3":     (297, 420),
    "8K":     (270, 390),
    "Letter": (216, 279),
    "Legal":  (216, 356),
    "B4":     (250, 353),
    "B5":     (176, 250),
    "4x6":    (102, 152),
    "5x7":    (127, 178),
}


class PrinterService:
    """
    CUPS 打印服务

    使用示例:
        >>> ps = PrinterService()
        >>> ps.check_printer()          # 检查打印机是否在线
        >>> job_id = ps.submit_job(     # 提交任务
        ...     pdf_path="/tmp/doc.pdf",
        ...     job_name="job-abc123",
        ...     options={"copies": 2, "sides": "two-sided-long-edge"}
        ... )
    """

    def __init__(self, printer_name: str | None = None):
        """
        初始化 CUPS 连接

        Args:
            printer_name: 打印机队列名 (默认从配置读取)
        """
        self.printer_name = printer_name or config.PRINTER_NAME
        self.conn: Optional[cups.Connection] = None
        self._connect()

    # ── 连接管理 ──────────────────────────────

    def _connect(self):
        """建立 CUPS 连接"""
        try:
            self.conn = cups.Connection()

            # 获取服务器地址 (兼容新旧版本 pycups)
            try:
                server = self.conn.getServer()
            except AttributeError:
                server = cups.getServer() if hasattr(cups, 'getServer') else cups.getDefault() or 'localhost'

            logger.info(f"CUPS 连接已建立, 服务器: {server}")

            # 列出所有可用打印机 (方便诊断)
            try:
                printers = self.conn.getPrinters()
                if printers:
                    names = ", ".join(printers.keys())
                    logger.info(f"检测到 CUPS 打印机: {names}")
                else:
                    logger.warning("CUPS 中无任何打印机队列! 请先添加打印机:")
                    logger.warning("  1. 浏览器打开 https://<树莓派IP>:631")
                    logger.warning("  2. Administration → Add Printer")
                    logger.warning("  3. 或命令行: lpadmin -p 打印机名 -E -v usb://... -m everywhere")
            except Exception:
                pass

        except Exception as e:
            logger.error(f"CUPS 连接失败: {e}")
            logger.error("请检查:")
            logger.error("  1. CUPS 服务是否运行?  sudo systemctl status cups")
            logger.error("  2. pycups 是否安装?  pip install pycups")
            logger.error("  3. 当前用户是否在 lpadmin 组?  sudo usermod -a -G lpadmin $USER")
            self.conn = None

    def reconnect(self):
        """重新连接 CUPS (打印机恢复后调用)"""
        logger.info("正在重新连接 CUPS...")
        self._connect()

    @property
    def is_connected(self) -> bool:
        """CUPS 连接是否已建立"""
        return self.conn is not None

    # ── 打印机状态检查 ────────────────────────

    def check_printer(self) -> tuple[bool, str]:
        """
        检查目标打印机是否在线且可用

        Returns:
            (是否可用, 状态描述)
        """
        if self.conn is None:
            return False, "CUPS 连接未建立"

        try:
            printers = self.conn.getPrinters()
            if self.printer_name not in printers:
                available = ", ".join(printers.keys()) if printers else "(无)"
                return False, f"打印机 '{self.printer_name}' 未找到。可用打印机: {available}"

            printer_info = printers[self.printer_name]
            state = printer_info.get("printer-state", -1)
            state_reasons = printer_info.get("printer-state-reasons", [])

            # CUPS 打印机状态码:
            #   3 = IDLE (就绪)
            #   4 = PRINTING (工作中)
            #   5 = STOPPED (已停止)
            state_names = {
                3: "就绪",
                4: "正在打印",
                5: "已停止",
            }
            state_desc = state_names.get(state, f"未知状态({state})")

            if state == 5:
                return False, f"打印机已停止 (原因: {state_reasons})"

            logger.info(f"打印机 '{self.printer_name}' 状态: {state_desc}")
            return True, state_desc

        except Exception as e:
            logger.error(f"检查打印机状态异常: {e}")
            return False, str(e)

    # ── 参数映射核心 ──────────────────────────

    def _map_options(self, cloud_options: dict) -> dict:
        """
        将云端 JSON 参数映射为 CUPS 标准选项字典

        映射示例:
          输入:  {"number_up": 2, "sides": "two-sided-long-edge", "copies": 3}
          输出:  {"number-up": "2", "sides": "two-sided-long-edge", "copies": "3"}

        规则:
          1. 所有值转换为字符串 (CUPS 要求)
          2. 跳过值为 None 的选项 (使用打印机默认值)
          3. 透传 _raw_options 中的原始 CUPS 参数

        Args:
            cloud_options: 来自云端的打印参数

        Returns:
            CUPS 格式的选项字典
        """
        if not cloud_options:
            return {}

        cups_options: dict[str, str] = {}

        for json_key, value in cloud_options.items():
            # ── 透传原始参数 (跳过内部 key) ──
            if json_key == "_raw_options":
                raw = value if isinstance(value, dict) else {}
                for raw_key, raw_val in raw.items():
                    cups_options[raw_key] = str(raw_val)
                continue

            # ── 查找映射规则 ──
            rule = CUPS_OPTION_MAP.get(json_key)
            if rule is None:
                logger.warning(f"忽略未知参数: {json_key}={value}")
                continue

            cups_key = rule["cups_key"]
            if cups_key is None:
                continue  # 仅内部标记

            # ── 跳过 None ──
            if value is None:
                continue

            # ── 类型校验 & 转换 ──
            try:
                typed_value = rule["type"](value)
            except (ValueError, TypeError):
                logger.warning(
                    f"参数 {json_key} 类型错误: 期望 {rule['type'].__name__}, "
                    f"实际 {type(value).__name__}。使用默认值 {rule['default']}"
                )
                typed_value = rule["default"]

            # ── 合法性校验 ──
            if rule["validator"] and not rule["validator"](typed_value):
                logger.warning(
                    f"参数 {json_key} 值不合法: {typed_value}。使用默认值 {rule['default']}"
                )
                typed_value = rule["default"]

            # ── CUPS 需要字符串类型 ──
            cups_options[cups_key] = str(typed_value)

        logger.debug(f"参数映射: {cloud_options} → {cups_options}")
        return cups_options

    # ── 提交打印作业 ──────────────────────────

    def submit_job(
        self,
        pdf_path: str,
        job_name: str,
        options: dict,
    ) -> int:
        """
        向 CUPS 提交打印任务

        Args:
            pdf_path: 本地 PDF 文件路径
            job_name: 作业名称 (用于 CUPS 队列显示)
            options: 云端 JSON 格式的打印参数

        Returns:
            CUPS 作业 ID (整数)

        Raises:
            RuntimeError: 打印机不可用或提交失败
        """
        # ── 0. 检查连接 ──
        if self.conn is None:
            raise RuntimeError("CUPS 连接未建立，无法提交打印")

        # ── 1. 检查打印机状态 ──
        available, msg = self.check_printer()
        if not available:
            raise RuntimeError(f"打印机不可用: {msg}")

        # ── 2. 参数映射 ──
        cups_options = self._map_options(options)

        # ── 2.5 物理缩放 PDF 页面到目标纸张 ──
        # CUPS 的 media/fit-to-page 选项取决于 PPD, 多数打印机忽略自定义尺寸。
        # 唯一 100% 可靠方案: 用 pypdf 直接改写 PDF 内部 MediaBox。
        # 这样无论 CUPS/PPD 如何, 送到打印机的每一页物理尺寸就是用户选的纸。
        media_name = options.get("media")
        if media_name and media_name in PAPER_DIMENSIONS_MM:
            w_mm, h_mm = PAPER_DIMENSIONS_MM[media_name]
            orientation = options.get("orientation", "portrait")
            # 横向: 交换宽高
            if orientation in ("landscape", "reverse-landscape"):
                w_mm, h_mm = h_mm, w_mm
            resized_path = self._resize_pdf_pages(pdf_path, w_mm, h_mm)
            if resized_path:
                pdf_path = str(resized_path)
                logger.info(
                    f"PDF 已缩放至 {media_name}: {w_mm}x{h_mm}mm"
                )
            cups_options["fit-to-page"] = "true"

        logger.info(f"打印参数: {cups_options}")

        # ── 3. 提交到 CUPS 队列 ──
        try:
            job_id = self.conn.printFile(
                self.printer_name,   # 目标队列
                pdf_path,            # PDF 文件
                job_name,            # 作业显示名
                cups_options,        # 打印选项
            )
            logger.info(
                f"✅ 打印作业已提交: CUPS Job #{job_id}, "
                f"文件: {pdf_path}, 队列: {self.printer_name}"
            )
            return job_id

        except cups.IPPError as e:
            raise RuntimeError(f"CUPS IPP 错误: {e}")
        except Exception as e:
            raise RuntimeError(f"提交打印作业失败: {e}")

    # ── PDF 页面物理缩放 ──────────────────────

    @staticmethod
    def _resize_pdf_pages(src_path: str, w_mm: int, h_mm: int) -> Path | None:
        """
        将 PDF 每一页的 MediaBox 改写为目标纸张尺寸

        pypdf 方案:
          1. 计算目标/当前的比例 (等比缩放)
          2. page.scale_by(ratio) — 同步缩放内容 + MediaBox
          3. 微调 MediaBox 到精确毫米值

        mm → points: 1mm = 72/25.4 pt

        Returns:
            缩放后的 PDF 路径, 失败返回 None
        """
        MM_TO_PT = 72 / 25.4

        try:
            reader = PdfReader(src_path)
            writer = PdfWriter()

            page_count = len(reader.pages)
            if page_count == 0:
                return None

            target_w = float(w_mm * MM_TO_PT)
            target_h = float(h_mm * MM_TO_PT)

            for page in reader.pages:
                old_w = float(page.mediabox.width)
                old_h = float(page.mediabox.height)

                # 等比缩放因子
                ratio = min(target_w / old_w, target_h / old_h)

                # scale_by: 同时缩放内容 + MediaBox (pypdf 标准 API)
                page.scale_by(ratio)

                # 微调 MediaBox 到精确目标尺寸
                page.mediabox = RectangleObject([0, 0, target_w, target_h])
                page.cropbox = RectangleObject([0, 0, target_w, target_h])

                writer.add_page(page)

            out_path = Path(src_path).with_suffix(".resized.pdf")
            with open(out_path, "wb") as f:
                writer.write(f)

            logger.debug(
                f"PDF 缩放完成: {page_count} 页 → "
                f"{w_mm}x{h_mm}mm ({target_w:.0f}x{target_h:.0f}pt) → {out_path}"
            )
            return out_path

        except Exception as e:
            logger.warning(f"PDF 物理缩放失败 (将继续使用原文件): {e}")
            return None

    # ── 获取作业状态 ──────────────────────────

    def get_job_status(self, job_id: int) -> dict:
        """
        查询 CUPS 作业状态

        Args:
            job_id: CUPS 作业 ID

        Returns:
            {"state": "completed", "printer": "...", "pages": 5}
        """
        if self.conn is None:
            return {"error": "CUPS 未连接"}

        try:
            attrs = self.conn.getJobAttributes(job_id)
            state = attrs.get("job-state", -1)

            state_names = {
                3: "pending",
                4: "pending-held",
                5: "processing",
                6: "processing-stopped",
                7: "canceled",
                8: "aborted",
                9: "completed",
            }

            return {
                "job_id": job_id,
                "state": state_names.get(state, f"unknown({state})"),
                "printer": attrs.get("job-printer-uri", ""),
                "pages": attrs.get("job-media-sheets-completed", 0),
                "name": attrs.get("job-name", ""),
            }
        except Exception as e:
            logger.error(f"获取作业状态失败: {e}")
            return {"error": str(e)}

    # ── 取消作业 ──────────────────────────────

    def cancel_job(self, job_id: int) -> bool:
        """取消指定 CUPS 作业"""
        if self.conn is None:
            return False
        try:
            self.conn.cancelJob(job_id)
            logger.info(f"已取消 CUPS Job #{job_id}")
            return True
        except Exception as e:
            logger.error(f"取消失败: {e}")
            return False
