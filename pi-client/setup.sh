#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 星火智造云打印 — 树莓派一键配置向导
# ═══════════════════════════════════════════════════════════════════════════════
#
# 用法:
#   bash setup.sh          图形化向导 (逐步引导)
#   bash setup.sh --quick  快速模式 (自动检测 + 少交互)
#
# 完成以下步骤:
#   1. 检查系统依赖 (Python3 / pip / CUPS / libcups2-dev)
#   2. 安装 Python 包 (pycups, requests, tenacity, python-dotenv)
#   3. 检测并配置 CUPS 打印机
#   4. 生成 .env 配置文件
#   5. 向云端注册节点
#   6. 启动测试 (心跳 + 拉取任务)
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

log_info()  { echo -e "  ${GREEN}[✓]${NC} $*"; }
log_warn()  { echo -e "  ${YELLOW}[!]${NC} $*"; }
log_error() { echo -e "  ${RED}[✗]${NC} $*"; }
log_step()  { echo -e "\n${CYAN}${BOLD}▶ $*${NC}"; }
log_title() { echo -e "${CYAN}${BOLD}$*${NC}"; }

# ── 全局变量 ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
QUICK_MODE=false
STEPS_TOTAL=6
STEP_CURRENT=0

for arg in "$@"; do
    case "$arg" in --quick|-q) QUICK_MODE=true ;; esac
done

# ═══════════════════════════════════════════════════════════════════════════════
# 欢迎
# ═══════════════════════════════════════════════════════════════════════════════

clear
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                  ║${NC}"
echo -e "${CYAN}║     星火智造云打印 — 树莓派配置向导             ║${NC}"
echo -e "${CYAN}║     Starfire Print Hub Pi Setup Wizard           ║${NC}"
echo -e "${CYAN}║                                                  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  本向导将引导你完成以下 ${STEPS_TOTAL} 个步骤:"
echo ""
echo "    1. 检查系统依赖"
echo "    2. 安装 Python 包"
echo "    3. 配置 CUPS 打印机"
echo "    4. 生成 .env 配置"
echo "    5. 向云端注册节点"
echo "    6. 启动验证"
echo ""

if ! $QUICK_MODE; then
    read -r -p "  按 Enter 开始配置..." _
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: 检查系统依赖
# ═══════════════════════════════════════════════════════════════════════════════
step_header() {
    STEP_CURRENT=$((STEP_CURRENT + 1))
    echo ""
    echo -e "${CYAN}┌──────────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│  步骤 ${STEP_CURRENT}/${STEPS_TOTAL}: $1${NC}"
    echo -e "${CYAN}└──────────────────────────────────────────────────┘${NC}"
}

step_header "检查系统依赖"

PASS_ALL=true

# Python3
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    log_info "Python3: $PY_VER"
else
    log_error "Python3 未安装!"
    echo "      sudo apt update && sudo apt install -y python3 python3-pip"
    PASS_ALL=false
fi

# pip
if command -v pip3 &>/dev/null; then
    log_info "pip3: 已安装"
else
    log_warn "pip3 未安装, 正在安装..."
    sudo apt update && sudo apt install -y python3-pip
    log_info "pip3 安装完成"
fi

# CUPS 服务
if systemctl is-active --quiet cups 2>/dev/null; then
    log_info "CUPS 服务: 运行中"
else
    log_warn "CUPS 服务未运行, 正在启动..."
    sudo systemctl enable cups 2>/dev/null || true
    sudo systemctl start cups 2>/dev/null || true
    sleep 2
    if systemctl is-active --quiet cups 2>/dev/null; then
        log_info "CUPS 服务: 已启动"
    else
        log_error "CUPS 服务启动失败!"
        echo "      sudo apt install -y cups && sudo systemctl enable cups && sudo systemctl start cups"
        PASS_ALL=false
    fi
fi

# libcups2-dev (编译 pycups 需要)
if dpkg -l libcups2-dev &>/dev/null 2>&1 || dpkg -l libcups2-dev:armhf &>/dev/null 2>&1; then
    log_info "libcups2-dev: 已安装"
else
    log_warn "libcups2-dev 未安装, 正在安装..."
    sudo apt update && sudo apt install -y libcups2-dev
    log_info "libcups2-dev 安装完成"
fi

# 用户组
if groups | grep -q lpadmin; then
    log_info "用户已在 lpadmin 组: ✓"
else
    log_warn "用户不在 lpadmin 组, 正在添加..."
    sudo usermod -a -G lpadmin "$USER"
    log_info "已添加。请注销后重新登录, 或运行: newgrp lpadmin"
fi

if ! $PASS_ALL; then
    echo ""
    log_error "关键依赖缺失, 请修复后重新运行。"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 2: 安装 Python 包
# ═══════════════════════════════════════════════════════════════════════════════

step_header "安装 Python 包"

REQUIRED_PKGS=("requests" "tenacity" "python-dotenv" "pycups")

for pkg in "${REQUIRED_PKGS[@]}"; do
    if python3 -c "import ${pkg//-/_}" &>/dev/null 2>&1; then
        log_info "$pkg: 已安装"
    else
        log_warn "$pkg 未安装, 正在安装..."
        pip3 install "$pkg" --break-system-packages 2>/dev/null || pip3 install "$pkg" --user
    fi
done

log_info "所有 Python 包就绪"

# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: 配置 CUPS 打印机
# ═══════════════════════════════════════════════════════════════════════════════

step_header "配置 CUPS 打印机"

# 列出可用打印机设备
echo ""
log_title "正在扫描打印机设备..."
echo ""

# USB 设备
USB_DEVICES=$(lpinfo -v 2>/dev/null | grep -i 'usb\|ipp\|dnssd\|socket' || echo "")
DETECTED_URI=""
DETECTED_MODEL=""

if [ -n "$USB_DEVICES" ]; then
    echo "  检测到以下打印设备:"
    echo ""
    idx=1
    mapfile -t lines <<< "$USB_DEVICES"
    for line in "${lines[@]}"; do
        echo -e "    ${GREEN}[$idx]${NC} $line"
        idx=$((idx + 1))
    done
    echo ""
    
    if $QUICK_MODE; then
        # 自动选第一个
        DETECTED_URI=$(echo "${lines[0]}" | awk '{print $NF}')
        DETECTED_MODEL=$(echo "${lines[0]}" | awk -F' ' '{for(i=2;i<NF;i++) printf "%s ", $i}')
        echo "  自动选择: $DETECTED_URI"
    else
        read -r -p "  选择设备编号 [1]: " choice
        choice=${choice:-1}
        if [ "$choice" -ge 1 ] 2>/dev/null && [ "$choice" -le "${#lines[@]}" ]; then
            DETECTED_URI=$(echo "${lines[$((choice-1))]}" | awk '{print $NF}')
        fi
    fi
else
    log_warn "未检测到 USB/IPP 打印机设备。"
    echo ""
    echo "  请确认打印机已连接并开机。"
    echo "  你也可以手动输入设备 URI 或稍后在 CUPS 管理页面添加。"
    echo "  浏览器打开: https://<树莓派IP>:631"
    echo ""
fi

# 现有 CUPS 队列
echo ""
CUPS_PRINTERS=$(python3 -c "import cups; c=cups.Connection(); [print(k) for k in c.getPrinters()]" 2>/dev/null || echo "")
EXISTING_PRINTER=""

if [ -n "$CUPS_PRINTERS" ]; then
    echo "  CUPS 中已有打印机:"
    while IFS= read -r p; do
        echo -e "    - ${GREEN}$p${NC}"
    done <<< "$CUPS_PRINTERS"
    # 用第一个已有打印机作为默认
    EXISTING_PRINTER=$(echo "$CUPS_PRINTERS" | head -1)
    echo ""
fi

# 决定打印机名称
if [ -n "$EXISTING_PRINTER" ]; then
    DEFAULT_NAME="$EXISTING_PRINTER"
    log_info "使用已有打印机: $DEFAULT_NAME"
    PRINTER_NAME="$DEFAULT_NAME"
elif [ -n "$DETECTED_URI" ]; then
    # 生成打印机名称
    HOSTNAME_SHORT=$(hostname | tr '-' '_')
    DEFAULT_NAME="${HOSTNAME_SHORT}_printer"
    
    if $QUICK_MODE; then
        PRINTER_NAME="$DEFAULT_NAME"
    else
        echo -e "  检测到设备, 建议打印机名称: ${GREEN}$DEFAULT_NAME${NC}"
        read -r -p "  打印机名称 (回车确认): " user_name
        PRINTER_NAME="${user_name:-$DEFAULT_NAME}"
    fi
    
    echo ""
    log_warn "正在添加打印机到 CUPS..."
    sudo lpadmin -p "$PRINTER_NAME" -E -v "$DETECTED_URI" -m everywhere 2>/dev/null || {
        # everywhere 驱动失败, 尝试 raw
        sudo lpadmin -p "$PRINTER_NAME" -E -v "$DETECTED_URI" -m raw
    }
    
    # 设为默认
    sudo lpadmin -d "$PRINTER_NAME" 2>/dev/null || true
    
    # 验证
    sleep 1
    if lpstat -p "$PRINTER_NAME" &>/dev/null 2>&1; then
        log_info "打印机 '$PRINTER_NAME' 添加成功!"
    else
        log_warn "打印机添加可能失败, 请稍后在 CUPS 管理页面手动添加"
    fi
else
    echo ""
    if $QUICK_MODE; then
        log_warn "无可用打印机, 跳过此步骤"
        PRINTER_NAME="Fuji_Xerox_SC2020"
    else
        read -r -p "  手动输入 CUPS 打印机名称 (如 Fuji_Xerox_SC2020): " PRINTER_NAME
        PRINTER_NAME="${PRINTER_NAME:-Fuji_Xerox_SC2020}"
    fi
fi

echo ""
log_info "打印机配置完成: $PRINTER_NAME"

# ═══════════════════════════════════════════════════════════════════════════════
# Step 4: 生成 .env 配置
# ═══════════════════════════════════════════════════════════════════════════════

step_header "生成 .env 配置文件"

# 检测 MAC
detect_mac() {
    for iface in eth0 end0 eth1 wlan0; do
        [ -f "/sys/class/net/$iface/address" ] && cat "/sys/class/net/$iface/address" && return
    done
    echo "02:$(cat /etc/machine-id 2>/dev/null | md5sum | head -c 2):00:00:00:01"
}
MAC=$(detect_mac)

# 生成 NODE_ID
HOSTNAME_SHORT=$(hostname)
NODE_ID_DEFAULT="pi-${HOSTNAME_SHORT}"

# 读取用户名输入
if $QUICK_MODE; then
    NODE_NAME_VAL="打印机-${HOSTNAME_SHORT}"
    CLOUD_URL_VAL="http://192.168.1.100:8000"
else
    read -r -p "  云端 API 地址 [http://192.168.1.100:8000]: " CLOUD_URL_VAL
    CLOUD_URL_VAL="${CLOUD_URL_VAL:-http://192.168.1.100:8000}"
    CLOUD_URL_VAL="${CLOUD_URL_VAL%/}"  # 去尾部斜杠
    
    read -r -p "  节点 ID [${NODE_ID_DEFAULT}]: " NODE_ID_VAL
    NODE_ID_VAL="${NODE_ID_VAL:-${NODE_ID_DEFAULT}}"
    
    read -r -p "  节点名称 [打印机-${HOSTNAME_SHORT}]: " NODE_NAME_VAL
    NODE_NAME_VAL="${NODE_NAME_VAL:-打印机-${HOSTNAME_SHORT}}"
fi

# 生成 .env
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "${ENV_FILE}.bak"
    log_info "已备份原 .env → .env.bak"
fi

cat > "$ENV_FILE" << DOTENV
# ── 云端 API ──
CLOUD_BASE_URL=${CLOUD_URL_VAL}

# ── 节点标识 ──
NODE_ID=${NODE_ID_VAL}
NODE_NAME=${NODE_NAME_VAL}

# ── 打印机队列名 (CUPS 中 lpstat -p 显示的打印机名称) ──
PRINTER_NAME=${PRINTER_NAME}

# ── 轮询间隔 (秒) ──
POLL_INTERVAL_SECONDS=5
POLL_LONG_INTERVAL_SECONDS=30

# ── 心跳间隔 (秒) ──
HEARTBEAT_INTERVAL_SECONDS=30

# ── 下载目录 ──
DOWNLOAD_DIR=/tmp/starfire-jobs
DOTENV

log_info ".env 配置已生成:"
echo ""
echo -e "  ${GREEN}CLOUD_BASE_URL${NC} = $CLOUD_URL_VAL"
echo -e "  ${GREEN}NODE_ID${NC}         = $NODE_ID_VAL"
echo -e "  ${GREEN}NODE_NAME${NC}       = $NODE_NAME_VAL"
echo -e "  ${GREEN}PRINTER_NAME${NC}    = $PRINTER_NAME"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Step 5: 向云端注册
# ═══════════════════════════════════════════════════════════════════════════════

step_header "向云端注册节点"

REGISTER_URL="${CLOUD_URL_VAL}/api/nodes/register"

echo "  正在注册..."
echo "  POST $REGISTER_URL"
echo ""

REGISTER_RESP=$(curl -s -w "\n%{http_code}" -X POST "$REGISTER_URL" \
    -G --data-urlencode "node_id=$NODE_ID_VAL" \
    --data-urlencode "name=$NODE_NAME_VAL" \
    --data-urlencode "printer_name=$PRINTER_NAME" \
    --connect-timeout 10 --max-time 30 2>&1 || echo "err\n000")

HTTP_CODE=$(echo "$REGISTER_RESP" | tail -1)
BODY=$(echo "$REGISTER_RESP" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo ""
    echo -e "  ${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "  ${GREEN}║  注册成功!                          ║${NC}"
    echo -e "  ${GREEN}╚══════════════════════════════════════╝${NC}"
    echo ""
    log_info "服务器响应:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
    echo ""
    log_error "注册失败 (HTTP $HTTP_CODE)"
    echo ""
    echo "  服务器响应:"
    echo "  $BODY" | head -5
    echo ""
    echo "  请检查:"
    echo "    1. 云端服务是否启动? curl $CLOUD_URL_VAL/health"
    echo "    2. 网络是否连通?  ping $(echo "$CLOUD_URL_VAL" | sed 's|.*://||;s|:.*||')"
    echo ""
    log_warn "你可以稍后运行: bash register.sh --auto --yes"
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 6: 启动验证
# ═══════════════════════════════════════════════════════════════════════════════

step_header "启动验证"

echo ""

# Python CUPS 测试
echo "  测试 CUPS 连接..."
CUPS_TEST=$(python3 -c "
import cups
c = cups.Connection()
printers = c.getPrinters()
if printers:
    print('OK|' + str(len(printers)) + '|' + ', '.join(printers.keys()))
else:
    print('EMPTY|0|')
" 2>&1 || echo "FAIL||")

CUPS_STATUS=$(echo "$CUPS_TEST" | cut -d'|' -f1)
CUPS_COUNT=$(echo "$CUPS_TEST" | cut -d'|' -f2)
CUPS_NAMES=$(echo "$CUPS_TEST" | cut -d'|' -f3)

case "$CUPS_STATUS" in
    OK)
        log_info "CUPS 连接成功, 检测到 $CUPS_COUNT 台打印机: $CUPS_NAMES"

        # 检查目标打印机
        if echo "$CUPS_NAMES" | grep -q "$PRINTER_NAME"; then
            log_info "目标打印机 '$PRINTER_NAME' 就绪"
        else
            log_error "目标打印机 '$PRINTER_NAME' 未在 CUPS 中找到!"
            echo "      CUPS 中的打印机: $CUPS_NAMES"
            echo "      请修改 .env 中 PRINTER_NAME 的值"
        fi
        ;;
    EMPTY)
        log_warn "CUPS 连接成功, 但没有任何打印机队列!"
        echo "      请添加打印机: sudo lpadmin -p $PRINTER_NAME -E -v <URI> -m everywhere"
        ;;
    *)
        log_error "CUPS 连接失败: $CUPS_TEST"
        echo "      1. sudo systemctl status cups"
        echo "      2. pip3 install pycups --break-system-packages"
        ;;
esac

echo ""

# 云端连通性
echo "  测试云端连通性..."
HEALTH_RESP=$(curl -s -o /dev/null -w "%{http_code}" "$CLOUD_URL_VAL/health" --connect-timeout 5 2>&1 || echo "000")
if [ "$HEALTH_RESP" = "200" ]; then
    log_info "云端服务可达 (HTTP 200)"
else
    log_warn "云端服务不可达 (HTTP $HEALTH_RESP)"
    echo "      curl $CLOUD_URL_VAL/health"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 完成
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                  ║${NC}"
echo -e "${GREEN}║    配置完成!                                     ║${NC}"
echo -e "${GREEN}║                                                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  配置文件:  $ENV_FILE"
echo "  打印机:    $PRINTER_NAME"
echo "  节点 ID:   $NODE_ID_VAL"
echo "  云端地址:  $CLOUD_URL_VAL"
echo ""
echo -e "  ${BOLD}启动守护进程:${NC}"
echo ""
echo "    cd $SCRIPT_DIR"
echo "    python3 pi_worker.py"
echo ""
echo -e "  ${BOLD}查看云端节点状态:${NC}"
echo ""
echo "    curl $CLOUD_URL_VAL/api/nodes/"
echo ""
echo -e "  ${BOLD}以后重新配置:${NC}"
echo ""
echo "    bash setup.sh        交互式引导"
echo "    bash register.sh     仅重新注册"
echo ""
echo -e "  ${BOLD}排查问题:${NC}"
echo ""
echo "    lpstat -p -d              查看 CUPS 打印机"
echo "    sudo systemctl status cups 查看 CUPS 服务状态"
echo "    python3 -c 'import cups; print(cups.Connection().getPrinters())'"
echo ""
