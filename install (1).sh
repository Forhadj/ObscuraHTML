#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  ObscuraHTML — Installer
#  Works on: Termux (Android), Ubuntu/Debian, Arch, macOS
#  Author  : Forhad Hassan (@Forhadj)
# ─────────────────────────────────────────────────────────────

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${GREEN}  ██████╗ ██████╗ ███████╗ ██████╗██╗   ██╗██████╗  █████╗ ${NC}"
echo -e "${GREEN} ██╔═══██╗██╔══██╗██╔════╝██╔════╝██║   ██║██╔══██╗██╔══██╗${NC}"
echo -e "${GREEN} ██║   ██║██████╔╝███████╗██║     ██║   ██║██████╔╝███████║${NC}"
echo -e "${GREEN} ██║   ██║██╔══██╗╚════██║██║     ██║   ██║██╔══██╗██╔══██║${NC}"
echo -e "${GREEN} ╚██████╔╝██████╔╝███████║╚██████╗╚██████╔╝██║  ██║██║  ██║${NC}"
echo -e "${GREEN}  ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝${NC}"
echo -e "${CYAN}       HTML Obfuscation Tool  |  by Forhad Hassan${NC}"
echo ""
echo -e "${CYAN}─────────────────────────────────────────────────${NC}"

# Detect environment
IS_TERMUX=false
if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ]; then
    IS_TERMUX=true
    echo -e "${YELLOW}[*] Detected: Termux (Android)${NC}"
else
    echo -e "${YELLOW}[*] Detected: Standard Linux / macOS${NC}"
fi

echo -e "${CYAN}[*] Installing dependencies...${NC}"

if $IS_TERMUX; then
    pip install rich pyfiglet pycryptodome 2>/dev/null \
        || pip install rich pyfiglet pycryptodome --break-system-packages
else
    pip3 install rich pyfiglet pycryptodome 2>/dev/null \
        || pip3 install rich pyfiglet pycryptodome --break-system-packages
fi

echo -e "${GREEN}[✓] Dependencies installed${NC}"

# Make executable
chmod +x obscura.py 2>/dev/null || true

echo ""
echo -e "${GREEN}─────────────────────────────────────────────────${NC}"
echo -e "${GREEN}  ✅  ObscuraHTML is ready!${NC}"
echo ""
echo -e "${CYAN}  Run with:${NC}"
echo -e "    ${YELLOW}python obscura.py${NC}          — from this directory"
echo -e "    ${YELLOW}python obscura.py --help${NC}   — show help"
echo ""
echo -e "${CYAN}  Or copy to PATH for global use:${NC}"
if $IS_TERMUX; then
    echo -e "    ${YELLOW}cp obscura.py \$PREFIX/bin/obscura && chmod +x \$PREFIX/bin/obscura${NC}"
else
    echo -e "    ${YELLOW}sudo cp obscura.py /usr/local/bin/obscura && sudo chmod +x /usr/local/bin/obscura${NC}"
fi
echo ""
echo -e "${GREEN}─────────────────────────────────────────────────${NC}"
