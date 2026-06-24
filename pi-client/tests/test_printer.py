"""
test_printer.py — CUPS 打印服务模块测试
覆盖: 参数映射(_map_options) / 打印机状态检查 / 作业提交

核心测试目标:
  - 验证云端 JSON 参数正确映射为 CUPS 标准选项
  - 验证未知参数被忽略、非法值回退默认值
  - 验证 CUPS 状态码解析正确
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# ── pi-client 路径 (使得 import printer 生效) ──
sys.path.insert(0, str(__file__).rsplit("tests", 1)[0])

# 在导入 printer 之前 mock cups 模块 (Windows 上 CUPS 不可用)
sys.modules["cups"] = MagicMock()

from printer import CUPS_OPTION_MAP, PrinterService  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
# 工具: 创建 mock PrinterService (无真实 CUPS 连接)
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def printer():
    """返回 _connect 被 bypass 的 PrinterService 实例"""
    svc = object.__new__(PrinterService)
    svc.printer_name = "Test_Printer"
    svc.conn = MagicMock()
    return svc


# ═══════════════════════════════════════════════════════════════════
# CUPS_OPTION_MAP 静态配置验证
# ═══════════════════════════════════════════════════════════════════

def test_option_map_has_all_expected_keys():
    expected = {
        "copies", "sides", "media", "number_up",
        "orientation", "page_ranges", "print_quality",
        "color_mode", "media_source", "media_type", "_raw_options",
    }
    assert set(CUPS_OPTION_MAP.keys()) == expected

    # 每个规则必须有 cups_key / type / default / validator
    for key, rule in CUPS_OPTION_MAP.items():
        assert "cups_key" in rule
        assert "type" in rule
        assert "default" in rule
        assert "validator" in rule


# ═══════════════════════════════════════════════════════════════════
# _map_options — 参数映射核心
# ═══════════════════════════════════════════════════════════════════

def test_map_options_empty_dict(printer):
    assert printer._map_options({}) == {}


def test_map_options_none_input(printer):
    assert printer._map_options(None) == {}


def test_map_options_basic_params(printer):
    cloud = {"copies": 3, "media": "A4", "sides": "one-sided"}
    result = printer._map_options(cloud)
    assert result == {"copies": "3", "media": "A4", "sides": "one-sided"}


def test_map_options_number_up_converts_key(printer):
    """验证云端 'number_up' → CUPS 'number-up'"""
    result = printer._map_options({"number_up": 4})
    assert result == {"number-up": "4"}


def test_map_options_all_params(printer):
    cloud = {
        "copies": 5,
        "sides": "two-sided-long-edge",
        "media": "Letter",
        "number_up": 2,
        "orientation": "landscape",
        "page_ranges": "1-3",
        "print_quality": "high",
        "color_mode": "monochrome",
    }
    result = printer._map_options(cloud)
    assert result == {
        "copies": "5",
        "sides": "two-sided-long-edge",
        "media": "Letter",
        "number-up": "2",
        "orientation-requested": "landscape",
        "page-ranges": "1-3",
        "print-quality": "high",
        "print-color-mode": "monochrome",
    }


def test_map_unknown_key_ignored(printer):
    result = printer._map_options({"copies": 1, "foo": "bar", "baz": 123})
    assert result == {"copies": "1"}
    assert "foo" not in result
    assert "baz" not in result


def test_map_none_values_skipped(printer):
    """page_ranges=None 时应跳过, 不写入 CUPS 选项"""
    result = printer._map_options({"copies": 1, "page_ranges": None})
    assert result == {"copies": "1"}
    assert "page-ranges" not in result


def test_map_invalid_type_falls_back_to_default(printer):
    """copies 应为 int, 传字符串 'abc' → 使用默认值 1"""
    result = printer._map_options({"copies": "not-a-number"})
    assert result == {"copies": "1"}


def test_map_invalid_value_falls_back_to_default(printer):
    """copies=0 不合法 (validator: 1~999) → 默认值"""
    result = printer._map_options({"copies": 0})
    assert result == {"copies": "1"}


def test_map_copies_max_boundary(printer):
    result = printer._map_options({"copies": 999})
    assert result == {"copies": "999"}


def test_map_copies_exceeds_boundary(printer):
    """copies=1000 超出上限 → 默认值 1"""
    result = printer._map_options({"copies": 1000})
    assert result == {"copies": "1"}


def test_map_number_up_valid_values(printer):
    for n in (1, 2, 4, 6, 9, 16):
        result = printer._map_options({"number_up": n})
        assert result == {"number-up": str(n)}


def test_map_number_up_invalid_value(printer):
    """number_up=3 不合法 → 默认值 1"""
    result = printer._map_options({"number_up": 3})
    assert result == {"number-up": "1"}


def test_map_raw_options_transparent(printer):
    cloud = {
        "copies": 1,
        "_raw_options": {"fit-to-page": "true", "scaling": "90"},
    }
    result = printer._map_options(cloud)
    assert result == {
        "copies": "1",
        "fit-to-page": "true",
        "scaling": "90",
    }


def test_map_raw_options_non_dict_ignored(printer):
    """_raw_options 传入非 dict 类型时应被忽略"""
    cloud = {"copies": 1, "_raw_options": "invalid"}
    result = printer._map_options(cloud)
    assert result == {"copies": "1"}


def test_map_orientation_all_valid(printer):
    for v in ("portrait", "landscape", "reverse-portrait", "reverse-landscape"):
        result = printer._map_options({"orientation": v})
        assert result == {"orientation-requested": v}


def test_map_sides_all_valid(printer):
    for v in ("one-sided", "two-sided-long-edge", "two-sided-short-edge"):
        result = printer._map_options({"sides": v})
        assert result == {"sides": v}


def test_map_quality_all_valid(printer):
    for v in ("draft", "normal", "high"):
        result = printer._map_options({"print_quality": v})
        assert result == {"print-quality": v}


def test_map_color_mode_all_valid(printer):
    for v in ("color", "monochrome", "auto"):
        result = printer._map_options({"color_mode": v})
        assert result == {"print-color-mode": v}


# ═══════════════════════════════════════════════════════════════════
# check_printer — 状态检查
# ═══════════════════════════════════════════════════════════════════

def test_check_printer_no_connection():
    svc = object.__new__(PrinterService)
    svc.printer_name = "Test"
    svc.conn = None

    available, msg = svc.check_printer()
    assert available is False
    assert "连接" in msg


def test_check_printer_not_found(printer):
    printer.conn.getPrinters.return_value = {"Other_Printer": {}}

    available, msg = printer.check_printer()
    assert available is False
    assert "未找到" in msg


def test_check_printer_idle(printer):
    printer.conn.getPrinters.return_value = {
        printer.printer_name: {
            "printer-state": 3,
            "printer-state-reasons": [],
        }
    }
    available, msg = printer.check_printer()
    assert available is True
    assert "就绪" in msg


def test_check_printer_printing(printer):
    """打印机正在工作中也应视为可用"""
    printer.conn.getPrinters.return_value = {
        printer.printer_name: {
            "printer-state": 4,
            "printer-state-reasons": [],
        }
    }
    available, msg = printer.check_printer()
    assert available is True
    assert "打印" in msg


def test_check_printer_stopped(printer):
    printer.conn.getPrinters.return_value = {
        printer.printer_name: {
            "printer-state": 5,
            "printer-state-reasons": ["media-jam"],
        }
    }
    available, msg = printer.check_printer()
    assert available is False
    assert "停止" in msg


# ═══════════════════════════════════════════════════════════════════
# submit_job — 作业提交
# ═══════════════════════════════════════════════════════════════════

def test_submit_job_success(printer):
    printer.conn.getPrinters.return_value = {
        printer.printer_name: {"printer-state": 3, "printer-state-reasons": []}
    }
    printer.conn.printFile.return_value = 42

    job_id = printer.submit_job(
        pdf_path="/tmp/doc.pdf",
        job_name="job-abc",
        options={"copies": 2},
    )
    assert job_id == 42

    printer.conn.printFile.assert_called_once_with(
        printer.printer_name,
        "/tmp/doc.pdf",
        "job-abc",
        {"copies": "2"},
    )


def test_submit_job_no_connection():
    svc = object.__new__(PrinterService)
    svc.printer_name = "Test"
    svc.conn = None

    with pytest.raises(RuntimeError, match="连接未建立"):
        svc.submit_job("/tmp/doc.pdf", "job", {})


def test_submit_job_printer_unavailable(printer):
    printer.conn.getPrinters.return_value = {
        printer.printer_name: {"printer-state": 5, "printer-state-reasons": ["offline"]}
    }
    with pytest.raises(RuntimeError, match="打印机不可用"):
        printer.submit_job("/tmp/doc.pdf", "job", {})


def test_submit_job_maps_options_before_submit(printer):
    """验证 _map_options 在 submit_job 中被正确调用"""
    printer.conn.getPrinters.return_value = {
        printer.printer_name: {"printer-state": 3, "printer-state-reasons": []}
    }
    printer.conn.printFile.return_value = 1

    printer.submit_job(
        pdf_path="/tmp/doc.pdf",
        job_name="job",
        options={"number_up": 4, "sides": "two-sided-long-edge"},
    )

    # 验证映射后的 CUPS 选项被传递
    printer.conn.printFile.assert_called_once()
    _, _, _, cups_opts = printer.conn.printFile.call_args[0]
    assert cups_opts["number-up"] == "4"
    assert cups_opts["sides"] == "two-sided-long-edge"


# ═══════════════════════════════════════════════════════════════════
# 纸张尺寸下发 — PageSize / media 双通道
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def printer_with_short_style(printer, tmp_path):
    """模拟支持简称 (A3/A4) 的 PPD 驱动打印机, 并 stub PDF 缩放"""
    printer.conn.getPrinters.return_value = {
        printer.printer_name: {"printer-state": 3, "printer-state-reasons": []}
    }
    printer.conn.getPrinterAttributes.return_value = {
        "media-supported": ["A3", "A4", "Letter", "8K"],
    }
    printer.conn.printFile.return_value = 99
    # 跳过真实的 PDF 改写, 让单测不依赖文件系统
    printer._resize_pdf_pages = MagicMock(return_value=None)
    return printer


@pytest.fixture
def printer_with_pwg_style(printer):
    """模拟仅支持 PWG 名 (iso_a3_*) 的 IPP-everywhere 打印机"""
    printer.conn.getPrinters.return_value = {
        printer.printer_name: {"printer-state": 3, "printer-state-reasons": []}
    }
    printer.conn.getPrinterAttributes.return_value = {
        "media-supported": ["iso_a3_297x420mm", "iso_a4_210x297mm"],
    }
    printer.conn.printFile.return_value = 100
    printer._resize_pdf_pages = MagicMock(return_value=None)
    return printer


def test_submit_job_a3_sets_both_pagesize_and_media(printer_with_short_style):
    """A3 下发必须同时设置 PageSize=A3 和 media=A3 — PPD 驱动只看 PageSize"""
    p = printer_with_short_style
    p.submit_job(
        pdf_path="/tmp/doc.pdf",
        job_name="job",
        options={"media": "A3", "copies": 1},
    )
    _, _, _, cups_opts = p.conn.printFile.call_args[0]
    # ── 核心断言: 必须有 PageSize 才能让 PPD 驱动选 A3 纸盒 ──
    assert cups_opts.get("PageSize") == "A3", \
        "缺失 PageSize → PPD 驱动会回退到默认 A4, 这正是 A3 被识别成 A4 的根因"
    assert cups_opts.get("media") == "A3"


def test_submit_job_8k_sets_pagesize(printer_with_short_style):
    """8K 是中国非标尺寸, 必须下发 PageSize=8K, 否则也会退化成 A4"""
    p = printer_with_short_style
    p.submit_job(
        pdf_path="/tmp/doc.pdf",
        job_name="job",
        options={"media": "8K", "copies": 1},
    )
    _, _, _, cups_opts = p.conn.printFile.call_args[0]
    assert cups_opts.get("PageSize") == "8K"
    assert cups_opts.get("media") == "8K"


def test_submit_job_a4_default_still_sets_pagesize(printer_with_short_style):
    """A4 也应明确下发 PageSize, 而非依赖打印机默认"""
    p = printer_with_short_style
    p.submit_job(
        pdf_path="/tmp/doc.pdf",
        job_name="job",
        options={"media": "A4"},
    )
    _, _, _, cups_opts = p.conn.printFile.call_args[0]
    assert cups_opts.get("PageSize") == "A4"
    assert cups_opts.get("media") == "A4"


def test_submit_job_pwg_only_uses_pwg_name_for_media(printer_with_pwg_style):
    """仅支持 PWG 名的现代打印机: media 用 iso_a3_*, PageSize 仍用简称"""
    p = printer_with_pwg_style
    p.submit_job(
        pdf_path="/tmp/doc.pdf",
        job_name="job",
        options={"media": "A3"},
    )
    _, _, _, cups_opts = p.conn.printFile.call_args[0]
    # media 走 PWG 路径
    assert cups_opts.get("media") == "iso_a3_297x420mm"
    # PageSize 始终是 PPD 风格简称
    assert cups_opts.get("PageSize") == "A3"


def test_submit_job_pwg_8k_falls_back_to_custom(printer_with_pwg_style):
    """8K 没有官方 PWG 名 → media 用 Custom.WxHmm 兜底"""
    p = printer_with_pwg_style
    p.submit_job(
        pdf_path="/tmp/doc.pdf",
        job_name="job",
        options={"media": "8K"},
    )
    _, _, _, cups_opts = p.conn.printFile.call_args[0]
    assert cups_opts.get("media") == "Custom.270x390mm"
    assert cups_opts.get("PageSize") == "8K"


def test_submit_job_does_not_send_fit_to_page(printer_with_short_style):
    """fit-to-page 必须被移除 — PDF 已物理缩放过, 再叠加会导致二次缩印"""
    p = printer_with_short_style
    p.submit_job(
        pdf_path="/tmp/doc.pdf",
        job_name="job",
        options={"media": "A3", "_raw_options": {"fit-to-page": "true"}},
    )
    _, _, _, cups_opts = p.conn.printFile.call_args[0]
    assert "fit-to-page" not in cups_opts


def test_detect_media_style_short_preferred_when_both_supported(printer):
    """同时暴露 PWG 与简称 → 优先选 short (兼容 PPD)"""
    printer.conn.getPrinterAttributes.return_value = {
        "media-supported": ["A3", "A4", "iso_a3_297x420mm", "iso_a4_210x297mm"],
    }
    assert printer._detect_media_style() == "short"


def test_detect_media_style_pwg_only(printer):
    printer.conn.getPrinterAttributes.return_value = {
        "media-supported": ["iso_a3_297x420mm", "iso_a4_210x297mm"],
    }
    assert printer._detect_media_style() == "pwg"


def test_detect_media_style_no_attrs(printer):
    """打印机不暴露 media-supported → custom 兜底"""
    printer.conn.getPrinterAttributes.return_value = {}
    assert printer._detect_media_style() == "custom"


def test_resolve_page_size_returns_short_name(printer):
    """PageSize 永远用简称, 不用 PWG"""
    # 即使 style 是 pwg, PageSize 也是简称
    printer._media_style_cache = "pwg"
    assert printer._resolve_page_size_value("A3", 297, 420) == "A3"
    assert printer._resolve_page_size_value("8K", 270, 390) == "8K"
