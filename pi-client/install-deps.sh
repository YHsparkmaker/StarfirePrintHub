#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 星火智造云打印 — 树莓派依赖一键安装
# ═══════════════════════════════════════════════════════════════════════════════
#
# 用法:
#   bash install-deps.sh          交互模式 (可选安装 TTS/DOC转换/SSH隧道工具)
#   bash install-deps.sh --all    安装全部 (含 TTS + LibreOffice + SSH 工具)
#   bash install-deps.sh --min    仅基础依赖 (CUPS + Python 包)
#   bash install-deps.sh --dry    仅检测, 不安装 (查看缺少什么)
#
# 安装内容:
#   【系统】Python3 / pip / CUPS / libcups2-dev / lpadmin 组
#   【Python】pycups / requests / tenacity / python-dotenv
#   【可选】espeak-ng (TTS 离线播报)
#   【可选】edge-tts + pygame + numpy (TTS 在线高质量播报)
#   【可选】libreoffice-impress (DOC 文件转换)
#   【可选】openssh-client + autossh (SSH 反向隧道)
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

log_ok()    { echo -e "  ${GREEN}[✓]${NC} $*"; }
log_skip()  { echo -e "  ${YELLOW}[○]${NC} $* (跳过)"; }
log_warn()  { echo -e "  ${YELLOW}[!]${NC} $*"; }
log_error() { echo -e "  ${RED}[✗]${NC} $*"; }
log_title() { echo -e "\n${CYAN}${BOLD}▶ $*${NC}"; }

# ── 模式判断 ──
MODE="interactive"
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --all) MODE="all" ;;
        --min) MODE="min" ;;
        --dry) DRY_RUN=true ;;
    esac
done

# ── 检测命令是否存在 ──
has() { command -v "$1" >/dev/null 2>&1; }

# ── 检测 deb 包是否已安装 ──
pkg_installed() { dpkg -s "$1" >/dev/null 2>&1; }

# ── 检测 pip 包是否已安装 ──
pip_installed() {
    python3 -c "import $1" 2>/dev/null
}

# dry-run 时的非安装操作
if $DRY_RUN; then
    DRY_APT="echo [dry] sudo apt install -y"
    DRY_PIP="echo [dry] pip3 install --break-system-packages"
else
    DRY_APT="sudo apt install -y"
    DRY_PIP="pip3 install --break-system-packages"
fi

# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║    星火智造云打印 — 树莓派依赖安装              ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

if $DRY_RUN; then
    log_warn "试运行模式: 只检测, 不安装"
fi

INSTALL_TTS=false
INSTALL_LIBREOFFICE=false
INSTALL_SSH_TOOLS=false

if [ "$MODE" = "all" ]; then
    INSTALL_TTS=true
    INSTALL_LIBREOFFICE=true
    INSTALL_SSH_TOOLS=true
    log_info "模式: 全部安装"
elif [ "$MODE" = "min" ]; then
    log_info "模式: 最小安装 (仅基础依赖)"
elif [ "$MODE" = "interactive" ]; then
    log_info "模式: 交互选择"
    echo ""
    echo "  除了基础依赖外, 你还需要安装以下可选组件吗?"
    echo ""
    read -r -p "  安装 TTS 语音播报 (espeak-ng + edge-tts)? [Y/n] " yn
    case "${yn:-y}" in [Yy]*) INSTALL_TTS=true ;; esac
    read -r -p "  安装 LibreOffice (DOC 文件转换)? [Y/n] " yn
    case "${yn:-y}" in [Yy]*) INSTALL_LIBREOFFICE=true ;; esac
    read -r -p "  安装 SSH 隧道工具 (openssh-client + autossh)? [Y/n] " yn
    case "${yn:-y}" in [Yy]*) INSTALL_SSH_TOOLS=true ;; esac
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════
# Step 1: 系统基础依赖
# ═══════════════════════════════════════════════════════════════════
log_title "1/5 系统基础依赖"

# ── Python3 ──
if has python3; then
    log_ok "Python3 $(python3 --version 2>&1)"
else
    log_warn "Python3 未安装, 正在安装..."
    $DRY_APT python3 python3-pip python3-venv
    log_ok "Python3 已安装"
fi

# ── pip ──
if has pip3; then
    log_ok "pip3 已就绪"
else
    $DRY_APT python3-pip
    log_ok "pip3 已安装"
fi

# ── CUPS ──
if has lpadmin && has lpinfo; then
    log_ok "CUPS 已就绪"
else
    log_warn "CUPS 未安装, 正在安装..."
    $DRY_APT cups cups-client
    sudo systemctl enable --now cups 2>/dev/null || true
    log_ok "CUPS 已安装并启动"
fi

# ── libcups2-dev (pycups 编译依赖) ──
if pkg_installed libcups2-dev; then
    log_ok "libcups2-dev 已安装"
else
    log_warn "libcups2-dev 未安装, 正在安装..."
    $DRY_APT libcups2-dev
    log_ok "libcups2-dev 已安装"
fi

# ── 将 pi 用户加入 lpadmin 组 ──
if groups | grep -q lpadmin; then
    log_ok "当前用户已在 lpadmin 组"
else
    log_warn "加入 lpadmin 组..."
    sudo usermod -a -G lpadmin "$USER" 2>/dev/null || sudo usermod -a -G lpadmin pi
    log_ok "已加入 lpadmin 组 (需重新登录生效)"
fi

# ── CUPS 允许远程管理 ──
if [ -f /etc/cups/cupsd.conf ]; then
    sudo sed -i 's/^Listen localhost:631$/Port 631/' /etc/cups/cupsd.conf 2>/dev/null || true
    sudo sed -i 's/Allow @LOCAL/Allow @LOCAL\n  Allow all/' /etc/cups/cupsd.conf 2>/dev/null || true
    sudo systemctl restart cups 2>/dev/null || true
fi

# ═══════════════════════════════════════════════════════════════════
# Step 2: Python 基础包
# ═══════════════════════════════════════════════════════════════════
log_title "2/5 Python 基础包"

PYTHON_BASE="requests python-dotenv tenacity"

for pkg in $PYTHON_BASE; do
    module="${pkg//-/_}"
    if pip_installed "$module"; then
        log_ok "$pkg"
    else
        log_warn "$pkg 未安装"
        $DRY_PIP "$pkg"
        log_ok "$pkg 已安装"
    fi
done

# pycups 特殊处理 (需要系统头文件)
if pip_installed "cups"; then
    log_ok "pycups"
else
    log_warn "pycups 未安装"
    $DRY_PIP pycups || {
        log_warn "pycups 编译失败, 尝试无缓存重装..."
        if ! $DRY_RUN; then
            pip3 install --no-cache-dir --force-reinstall pycups --break-system-packages 2>/dev/null || log_error "pycups 安装失败, 请确认 libcups2-dev 已安装"
        fi
    }
    pip_installed "cups" && log_ok "pycups 已安装" || log_error "pycups 仍未安装"
fi

# ═══════════════════════════════════════════════════════════════════
# Step 3: TTS 语音播报 (可选)
# ═══════════════════════════════════════════════════════════════════
if $INSTALL_TTS; then
    log_title "3/5 TTS 语音播报"

    # espeak-ng (离线首选)
    if has espeak-ng; then
        log_ok "espeak-ng"
    else
        log_warn "安装 espeak-ng..."
        $DRY_APT espeak-ng
        has espeak-ng && log_ok "espeak-ng 已安装" || log_error "espeak-ng 安装失败"
    fi

    # edge-tts (在线高质量, 需 pip)
    if pip_installed "edge_tts"; then
        log_ok "edge-tts"
    else
        log_warn "安装 edge-tts..."
        $DRY_PIP edge-tts
        pip_installed "edge_tts" && log_ok "edge-tts 已安装" || log_warn "edge-tts 安装失败 (非阻塞)"
    fi

    # pygame + numpy (蜂鸣回退, 可选)
    if pip_installed "pygame"; then
        log_ok "pygame"
    else
        log_warn "安装 pygame..."
        $DRY_APT python3-pygame 2>/dev/null || $DRY_PIP pygame
        log_ok "pygame 已安装"
    fi

    if pip_installed "numpy"; then
        log_ok "numpy"
    else
        log_warn "安装 numpy..."
        $DRY_PIP numpy
        log_ok "numpy 已安装"
    fi

else
    log_title "3/5 TTS 语音播报"
    log_skip "TTS 未选择安装"
fi

# ═══════════════════════════════════════════════════════════════════
# Step 4: DOC 文件转换 (可选)
# ═══════════════════════════════════════════════════════════════════
if $INSTALL_LIBREOFFICE; then
    log_title "4/5 DOC 文件转换"

    if has libreoffice; then
        log_ok "LibreOffice"
    else
        log_warn "安装 LibreOffice (约 250MB, 请耐心等待)..."
        $DRY_APT libreoffice-impress
        has libreoffice && log_ok "LibreOffice 已安装" || log_error "LibreOffice 安装失败"
    fi

    # antiword (轻量 DOC 文本提取)
    if has antiword; then
        log_ok "antiword"
    else
        $DRY_APT antiword 2>/dev/null && log_ok "antiword 已安装" || log_skip "antiword (未安装)"
    fi
else
    log_title "4/5 DOC 文件转换"
    log_skip "LibreOffice 未选择安装"
fi

# ═══════════════════════════════════════════════════════════════════
# Step 5: SSH 反向隧道 (可选)
# ═══════════════════════════════════════════════════════════════════
if $INSTALL_SSH_TOOLS; then
    log_title "5/5 SSH 反向隧道"

    if has ssh; then
        log_ok "openssh-client"
    else
        $DRY_APT openssh-client
        log_ok "openssh-client 已安装"
    fi

    if has autossh; then
        log_ok "autossh"
    else
        $DRY_APT autossh
        has autossh && log_ok "autossh 已安装" || log_skip "autossh (未安装)"
    fi

    # 生成密钥对 (如果没有)
    if [ ! -f ~/.ssh/id_rsa ]; then
        if ! $DRY_RUN; then
            echo ""
            echo -e "  ${YELLOW}未检测到 SSH 密钥对, 自动生成...${NC}"
            ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -q
        fi
        log_ok "SSH 密钥对已生成"
    else
        log_ok "SSH 密钥对已就绪"
    fi
else
    log_title "5/5 SSH 反向隧道"
    log_skip "SSH 工具未选择安装"
fi

# ═══════════════════════════════════════════════════════════════════
# 完成
# ═══════════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}    依赖安装完成!${NC}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════${NC}"
echo ""
echo "  已安装的组件:"
echo ""

echo -n "    系统基础:     "
has python3 && echo -e "${GREEN}Python3${NC}" || echo -e "${RED}FAIL${NC}"
echo -n "    CUPS:          "
has lpadmin && echo -e "${GREEN}已就绪${NC}" || echo -e "${RED}FAIL${NC}"
echo -n "    Python 基础包: "
pip_installed "requests" && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
echo -n "    pycups:        "
pip_installed "cups" && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"

if $INSTALL_TTS; then
    echo -n "    espeak-ng:     "
    has espeak-ng && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}未安装${NC}"
    echo -n "    edge-tts:      "
    pip_installed "edge_tts" && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}未安装${NC}"
    echo -n "    pygame:        "
    pip_installed "pygame" && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}未安装${NC}"
fi

if $INSTALL_LIBREOFFICE; then
    echo -n "    LibreOffice:   "
    has libreoffice && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}未安装${NC}"
fi

if $INSTALL_SSH_TOOLS; then
    echo -n "    SSH + autossh: "
    has autossh && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}基本OK${NC}"
fi

echo ""
echo "  下一步:"
echo "    bash setup.sh           运行配置向导"
echo "    sudo bash install-services.sh pi   安装开机自启动"
echo ""
