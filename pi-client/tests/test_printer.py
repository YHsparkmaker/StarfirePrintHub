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
