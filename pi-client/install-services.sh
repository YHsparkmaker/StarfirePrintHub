#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 星火智造云打印 — 自启动服务安装脚本
# ═══════════════════════════════════════════════════════════════════════════════
#
# 用法:
#   sudo bash install-services.sh all      安装全部服务 (云端 + 树莓派)
#   sudo bash install-services.sh pi       仅安装树莓派守护
#   sudo bash install-services.sh cloud    仅安装云端 API
#   sudo bash install-services.sh status   查看服务状态
#   sudo bash install-services.sh logs     查看日志
#   sudo bash install-services.sh remove   卸载所有服务
#
# 安装后:
#   - 树莓派: 开机自动启动 pi_worker.py, 崩溃自动重启
#   - 云端:   开机自动启动 FastAPI 服务, 崩溃自动重启
#   - 管理:   systemctl start|stop|restart|status starfire-pi
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "  ${GREEN}[✓]${NC} $*"; }
log_error() { echo -e "  ${RED}[✗]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PI_SERVICE="starfire-pi"
CLOUD_SERVICE="starfire-cloud"
DEV_SERVICE="starfire-dev"

MODE="${1:-all}"

# ═══════════════════════════════════════════════════════════════════
# 安装函数
# ═══════════════════════════════════════════════════════════════════

install_pi() {
    echo -e "\n${CYAN}▶ 安装树莓派守护服务: $PI_SERVICE${NC}"
    cp "$SCRIPT_DIR/starfire-pi.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable "$PI_SERVICE"
    systemctl restart "$PI_SERVICE"
    sleep 2
    if systemctl is-active --quiet "$PI_SERVICE"; then
        log_info "$PI_SERVICE 已启动"
    else
        log_error "$PI_SERVICE 启动失败, 查看日志: journalctl -u $PI_SERVICE -n 20"
    fi
}

install_cloud() {
    echo -e "\n${CYAN}▶ 安装云端 API 服务: $CLOUD_SERVICE${NC}"
    cp "$SCRIPT_DIR/starfire-cloud.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable "$CLOUD_SERVICE"
    systemctl restart "$CLOUD_SERVICE"
    sleep 2
    if systemctl is-active --quiet "$CLOUD_SERVICE"; then
        log_info "$CLOUD_SERVICE 已启动"
    else
        log_error "$CLOUD_SERVICE 启动失败, 查看日志: journalctl -u $CLOUD_SERVICE -n 20"
    fi
}

install_dev() {
    echo -e "\n${CYAN}▶ 安装前端 Dev 服务: $DEV_SERVICE${NC}"
    cp "$SCRIPT_DIR/starfire-dev.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable "$DEV_SERVICE"
    systemctl restart "$DEV_SERVICE"
    sleep 2
    if systemctl is-active --quiet "$DEV_SERVICE"; then
        log_info "$DEV_SERVICE 已启动"
    else
        log_error "$DEV_SERVICE 启动失败, 查看日志: journalctl -u $DEV_SERVICE -n 20"
    fi
}

show_status() {
    echo -e "\n${CYAN}▶ 服务状态${NC}\n"
    for svc in "$PI_SERVICE" "$CLOUD_SERVICE" "$DEV_SERVICE"; do
        if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
            active=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
            echo -e "  $(if [ "$active" = "active" ]; then echo "${GREEN}●${NC}"; else echo "${RED}○${NC}"; fi) $svc: $active"
        fi
    done
    echo ""
}

show_logs() {
    echo -e "\n${CYAN}▶ 最近日志${NC}\n"
    for svc in "$PI_SERVICE" "$CLOUD_SERVICE"; do
        if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
            echo -e "  ${CYAN}── $svc ──${NC}"
            journalctl -u "$svc" --no-pager -n 5 2>/dev/null || echo "   (无日志)"
            echo ""
        fi
    done
}

remove_services() {
    echo -e "\n${CYAN}▶ 卸载所有服务${NC}"
    for svc in "$PI_SERVICE" "$CLOUD_SERVICE" "$DEV_SERVICE"; do
        if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
            systemctl stop "$svc" 2>/dev/null || true
            systemctl disable "$svc" 2>/dev/null || true
            rm -f "/etc/systemd/system/$svc.service"
            log_info "已卸载: $svc"
        fi
    done
    systemctl daemon-reload
    log_info "卸载完成"
}

# ═══════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════

if [ "$(id -u)" -ne 0 ]; then
    echo "请使用 sudo 运行: sudo bash install-services.sh $MODE"
    exit 1
fi

case "$MODE" in
    all)
        echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
        echo -e "${CYAN}    星火智造云打印 — 一键安装自启动服务${NC}"
        echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
        install_pi
        install_cloud
        show_status
        ;;
    pi)
        install_pi
        show_status
        ;;
    cloud)
        install_cloud
        show_status
        ;;
    dev)
        install_dev
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    remove|uninstall)
        remove_services
        ;;
    *)
        echo "用法: sudo bash install-services.sh [all|pi|cloud|dev|status|logs|remove]"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}常用管理命令:${NC}"
echo "  sudo systemctl status starfire-pi    查看树莓派守护状态"
echo "  sudo systemctl restart starfire-pi   重启树莓派守护"
echo "  sudo systemctl status starfire-cloud 查看云端 API 状态"
echo "  sudo systemctl restart starfire-cloud 重启云端 API"
echo "  journalctl -u starfire-pi -f         实时查看日志"
echo "  journalctl -u starfire-cloud -f      实时查看云端日志"
