#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 星火智造云打印 — 树莓派设备注册脚本
# ═══════════════════════════════════════════════════════════════════════════════
#
# 功能: 自动向云端注册本机为边缘打印节点
#   - 自动检测 MAC 地址
#   - 支持交互式输入 / 命令行参数 / .env 配置三种模式
#   - 注册成功后自动将 node_id 写入 .env
#   - 可重复执行 (已注册则更新信息)
#
# 用法:
#   bash register.sh                         交互式
#   bash register.sh --auto --yes            全自动 (从 .env 读取所有参数)
#   bash register.sh --name "3楼A区" \       命令行指定
#                     --printer "Fuji_Xerox" \
#                     --cloud "http://192.168.1.100:8000"
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── 颜色输出 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

# ═══════════════════════════════════════════════════════════════════════════════
# 1. 确定脚本目录 & .env 路径
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# ═══════════════════════════════════════════════════════════════════════════════
# 2. 解析命令行参数
# ═══════════════════════════════════════════════════════════════════════════════

AUTO_MODE=false
AUTO_YES=false
ARG_NAME=""
ARG_PRINTER=""
ARG_CLOUD=""
ARG_MEDIA="A4"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto)
            AUTO_MODE=true
            shift
            ;;
        --yes|-y)
            AUTO_YES=true
            shift
            ;;
        --name)
            ARG_NAME="$2"
            shift 2
            ;;
        --printer)
            ARG_PRINTER="$2"
            shift 2
            ;;
        --cloud)
            ARG_CLOUD="$2"
            shift 2
            ;;
        --media)
            ARG_MEDIA="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --auto              从 .env 自动读取所有参数"
            echo "  --yes, -y           跳过所有确认提示 (配合 --auto)"
            echo "  --name NAME         节点名称, 如 '3楼A区打印机'"
            echo "  --printer NAME      CUPS 打印机队列名, 如 'Fuji_Xerox_SC2020'"
            echo "  --cloud URL         云端 API 地址, 如 'http://192.168.1.100:8000'"
            echo "  --media SIZE        默认纸张尺寸, 默认 A4"
            echo "  --help, -h          显示此帮助"
            echo ""
            echo "示例:"
            echo "  bash register.sh                          # 交互式输入"
            echo "  bash register.sh --auto --yes             # 全自动"
            echo "  bash register.sh --name '2楼B区' \\"
            echo "                    --cloud 'http://10.0.0.5:8000'"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════════
# 3. 检测 MAC 地址 (优先有线 eth0, 其次 wlan0)
# ═══════════════════════════════════════════════════════════════════════════════

detect_mac_address() {
    local mac=""

    # 尝试 eth0 / end0 (Pi 5)
    for iface in eth0 end0 eth1 wlan0; do
        if [ -d "/sys/class/net/$iface" ]; then
            mac=$(cat "/sys/class/net/$iface/address" 2>/dev/null || true)
            if [ -n "$mac" ] && [ "$mac" != "00:00:00:00:00:00" ]; then
                log_info "检测到网卡 $iface → MAC: $mac"
                echo "$mac"
                return 0
            fi
        fi
    done

    # 备选: ip link (raspbian)
    if command -v ip &>/dev/null; then
        mac=$(ip link show | grep -oP 'link/ether \K[0-9a-f:]{17}' | grep -v '00:00:00:00:00:00' | head -1)
        if [ -n "$mac" ]; then
            log_info "通过 ip link 检测到 MAC: $mac"
            echo "$mac"
            return 0
        fi
    fi

    # 备选: ifconfig
    if command -v ifconfig &>/dev/null; then
        mac=$(ifconfig | grep -oP 'ether \K[0-9a-f:]{17}' | grep -v '00:00:00:00:00:00' | head -1)
        if [ -n "$mac" ]; then
            log_info "通过 ifconfig 检测到 MAC: $mac"
            echo "$mac"
            return 0
        fi
    fi

    # 兜底: 生成稳定假 MAC (基于 machine-id)
    local machine_id=""
    if [ -f /etc/machine-id ]; then
        machine_id=$(cat /etc/machine-id)
    elif [ -f /var/lib/dbus/machine-id ]; then
        machine_id=$(cat /var/lib/dbus/machine-id)
    else
        machine_id=$(hostname)
    fi
    mac="02:$(echo "$machine_id" | md5sum | head -c 2):$(echo "$machine_id" | md5sum | tail -c 5 | sed 's/../&:/g;s/:$//' | head -c 8)"
    log_warn "未能检测到真实 MAC, 使用 machine-id 生成: $mac"
    echo "$mac"
}

MAC_ADDRESS=$(detect_mac_address)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. 读取 .env (如果存在)
# ═══════════════════════════════════════════════════════════════════════════════

load_env() {
    if [ -f "$ENV_FILE" ]; then
        # shellcheck disable=SC2046
        set -a
        # 只加载需要的变量, 过滤注释和空行
        while IFS='=' read -r key value; do
            key=$(echo "$key" | xargs)
            case "$key" in
                ""|\#*) continue ;;
                CLOUD_BASE_URL|NODE_ID|NODE_NAME|PRINTER_NAME) export "$key=$value" ;;
            esac
        done < "$ENV_FILE"
        set +a
        log_info "已加载配置: $ENV_FILE"
    fi
}

load_env

# ── 确定 NODE_ID ──
if [ -z "${NODE_ID:-}" ]; then
    NODE_ID="pi-$(hostname)"
    log_warn "未设置 NODE_ID, 使用自动生成: $NODE_ID"
else
    log_info "使用 NODE_ID: $NODE_ID"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 5. 收集参数
# ═══════════════════════════════════════════════════════════════════════════════

# 优先级: 命令行 > .env > 提示输入
get_value() {
    local arg_val="$1"
    local env_val="$2"
    local prompt="$3"

    if [ -n "$arg_val" ]; then
        echo "$arg_val"
    elif [ -n "${env_val:-}" ]; then
        echo "$env_val"
    elif $AUTO_MODE; then
        # 自动模式下没有值就报错
        log_error "缺少参数: $prompt"
        log_error "请在 .env 中设置或通过命令行传入"
        exit 1
    else
        read -r -p "  $prompt: " user_input
        echo "$user_input"
    fi
}

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  星火智造云打印 — 边缘节点注册工具      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

log_step "检测到 MAC 地址: $MAC_ADDRESS"
echo ""

if ! $AUTO_YES && ! $AUTO_MODE; then
    log_step "请填写节点信息 (回车使用默认值):"
    echo ""
fi

NODE_NAME=$(get_value "$ARG_NAME" "${NODE_NAME:-}" "节点名称 (如: 3楼A区打印机)")
PRINTER_NAME=$(get_value "$ARG_PRINTER" "${PRINTER_NAME:-Fuji_Xerox_SC2020}" "CUPS 打印机队列名")
CLOUD_URL=$(get_value "$ARG_CLOUD" "${CLOUD_BASE_URL:-http://192.168.1.100:8000}" "云端 API 地址")
MEDIA=$(get_value "$ARG_MEDIA" "A4" "默认纸张尺寸 [A4]")
MEDIA=${MEDIA:-A4}

# 去除尾部斜杠
CLOUD_URL="${CLOUD_URL%/}"

echo ""
log_info "──────────────────────────────────────────"
log_info "  节点名称:    $NODE_NAME"
log_info "  打印机:      $PRINTER_NAME"
log_info "  云端地址:    $CLOUD_URL"
log_info "  MAC 地址:    $MAC_ADDRESS"
log_info "  默认纸张:    $MEDIA"
log_info "──────────────────────────────────────────"
echo ""

if ! $AUTO_YES; then
    read -r -p "确认注册? [Y/n] " confirm
    confirm=${confirm:-Y}
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_warn "已取消注册"
        exit 0
    fi
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 6. 调用云端注册 API
# ═══════════════════════════════════════════════════════════════════════════════

REGISTER_URL="$CLOUD_URL/api/nodes/register"
QUERY_STRING="node_id=$NODE_ID&name=$NODE_NAME&mac_address=$MAC_ADDRESS&printer_name=$PRINTER_NAME&supported_media=$MEDIA"
FULL_URL="$REGISTER_URL?$QUERY_STRING"

log_step "正在注册到云端..."
log_info "POST $FULL_URL"
echo ""

# URL 编码节点名称 (处理中文)
urlencode() {
    python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$1" 2>/dev/null \
        || echo "$1"  # 如果 python3 不可用, 直接返回原文
}

ENCODED_NAME=$(urlencode "$NODE_NAME")
ENCODED_PRINTER=$(urlencode "$PRINTER_NAME")
ENCODED_MEDIA=$(urlencode "$MEDIA")
QUERY_STRING="node_id=${NODE_ID}&name=${ENCODED_NAME}&mac_address=${MAC_ADDRESS}&printer_name=${ENCODED_PRINTER}&supported_media=${ENCODED_MEDIA}"
FULL_URL="$REGISTER_URL?$QUERY_STRING"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$FULL_URL" \
    -H "User-Agent: StarfirePiRegister/1.0" \
    --connect-timeout 10 \
    --max-time 30 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  注册成功!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo ""

    # 解析 node_id
    NODE_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['node_id'])" 2>/dev/null || echo "")
    REG_NAME=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])" 2>/dev/null || echo "")

    if [ -z "$NODE_ID" ]; then
        # 回退: grep 提取
        NODE_ID=$(echo "$BODY" | grep -oP '"node_id"\s*:\s*"\K[^"]+' || echo "unknown")
    fi

    log_info "分配的节点 ID: ${GREEN}$NODE_ID${NC}"
    log_info "节点名称:     $REG_NAME"
    echo ""

    # ═══════════════════════════════════════════════════════════════════
    # 7. 写入 .env
    # ═══════════════════════════════════════════════════════════════════

    if [ -f "$ENV_FILE" ]; then
        # 更新已有 .env
        if grep -q "^NODE_ID=" "$ENV_FILE"; then
            sed -i "s/^NODE_ID=.*/NODE_ID=$NODE_ID/" "$ENV_FILE"
        else
            echo "NODE_ID=$NODE_ID" >> "$ENV_FILE"
        fi
        if grep -q "^NODE_NAME=" "$ENV_FILE"; then
            sed -i "s/^NODE_NAME=.*/NODE_NAME=$NODE_NAME/" "$ENV_FILE"
        else
            echo "NODE_NAME=$NODE_NAME" >> "$ENV_FILE"
        fi
        if grep -q "^CLOUD_BASE_URL=" "$ENV_FILE"; then
            # 用 | 作分隔符避免 URL 中 / 冲突
            sed -i "s|^CLOUD_BASE_URL=.*|CLOUD_BASE_URL=$CLOUD_URL|" "$ENV_FILE"
        else
            echo "CLOUD_BASE_URL=$CLOUD_URL" >> "$ENV_FILE"
        fi
        if grep -q "^PRINTER_NAME=" "$ENV_FILE"; then
            sed -i "s/^PRINTER_NAME=.*/PRINTER_NAME=$PRINTER_NAME/" "$ENV_FILE"
        else
            echo "PRINTER_NAME=$PRINTER_NAME" >> "$ENV_FILE"
        fi
        log_info "已更新 .env 文件: $ENV_FILE"
    else
        # 从 .env.example 复制并填充
        if [ -f "$SCRIPT_DIR/.env.example" ]; then
            cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
            sed -i "s/^NODE_ID=.*/NODE_ID=$NODE_ID/" "$ENV_FILE"
            sed -i "s/^NODE_NAME=.*/NODE_NAME=$NODE_NAME/" "$ENV_FILE"
            sed -i "s|^CLOUD_BASE_URL=.*|CLOUD_BASE_URL=$CLOUD_URL|" "$ENV_FILE"
            sed -i "s/^PRINTER_NAME=.*/PRINTER_NAME=$PRINTER_NAME/" "$ENV_FILE"
            log_info "已创建 .env 文件: $ENV_FILE"
        else
            cat > "$ENV_FILE" << DOTENV
# ── 云端 API ──
CLOUD_BASE_URL=$CLOUD_URL

# ── 节点标识 ──
NODE_ID=$NODE_ID
NODE_NAME=$NODE_NAME

# ── 打印机队列名 ──
PRINTER_NAME=$PRINTER_NAME

# ── 轮询间隔 (秒) ──
POLL_INTERVAL_SECONDS=5
POLL_LONG_INTERVAL_SECONDS=30

# ── 心跳间隔 (秒) ──
HEARTBEAT_INTERVAL_SECONDS=30

# ── 下载目录 ──
DOWNLOAD_DIR=/tmp/starfire-jobs
DOTENV
            log_info "已创建 .env 文件: $ENV_FILE"
        fi
    fi

    # ═══════════════════════════════════════════════════════════════════
    # 8. 验证连接 — 发送一次心跳
    # ═══════════════════════════════════════════════════════════════════
    echo ""
    log_step "测试心跳连接..."
    HEARTBEAT_RESP=$(curl -s -X POST "$CLOUD_URL/api/nodes/$NODE_ID/heartbeat" \
        -H "User-Agent: StarfirePiRegister/1.0" \
        --connect-timeout 5 \
        --max-time 10 2>&1 || echo "FAIL")

    if echo "$HEARTBEAT_RESP" | grep -q "is_online"; then
        log_info "心跳测试通过!"
    else
        log_warn "心跳测试未收到预期响应 (节点可能尚未正常通信, 不影响注册)"
    fi

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  注册完成! 可启动守护进程:              ║${NC}"
    echo -e "${GREEN}║                                          ║${NC}"
    echo -e "${GREEN}║    python3 pi_worker.py                  ║${NC}"
    echo -e "${GREEN}║                                          ║${NC}"
    echo -e "${GREEN}║  查看状态:                               ║${NC}"
    echo -e "${GREEN}║    curl $CLOUD_URL/api/nodes/            ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"

else
    echo -e "${RED}═══════════════════════════════════════════${NC}"
    echo -e "${RED}  注册失败 (HTTP $HTTP_CODE)${NC}"
    echo -e "${RED}═══════════════════════════════════════════${NC}"
    echo ""
    log_error "服务器响应:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    echo ""
    log_error "请检查:"
    echo "  1. 云端服务是否已启动?  (curl $CLOUD_URL/health)"
    echo "  2. 网络是否连通?        (ping $(echo "$CLOUD_URL" | sed 's|.*://||;s|:.*||'))"
    echo "  3. 防火墙是否放行 8000 端口?"
    echo ""
    exit 1
fi
