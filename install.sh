#!/usr/bin/env bash
# ============================================================
#  LLM PAPER TRADER — ONE-CLICK INSTALLER (Linux Mint / Ubuntu)
# ============================================================
set -e
C='\033[0;36m';G='\033[0;32m';Y='\033[1;33m';R='\033[0;31m';N='\033[0m'

echo -e "${C}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   LLM PAPER TRADER — AI CRYPTO AGENT          ║"
echo "  ║   Installer for Linux (NVIDIA GPU)          ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${N}"

echo -e "${Y}[1/6] Checking Python 3.10+...${N}"
if ! command -v python3 &>/dev/null; then
    sudo apt-get update -q && sudo apt-get install -y python3 python3-pip python3-venv
fi
PYV=$(python3 -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${G}  ✓ Python $PYV${N}"

echo -e "${Y}[2/6] Creating virtual environment...${N}"
python3 -m venv venv
source venv/bin/activate
echo -e "${G}  ✓ venv ready${N}"

echo -e "${Y}[3/6] Installing packages...${N}"
pip install --upgrade pip -q
pip install flask pyyaml ccxt requests -q
echo -e "${G}  ✓ Packages installed${N}"

echo -e "${Y}[4/6] Checking Ollama...${N}"
if command -v ollama &>/dev/null; then
    echo -e "${G}  ✓ Ollama already installed${N}"
else
    echo -e "${Y}  Ollama not found — installing...${N}"
    curl -fsSL https://ollama.ai/install.sh | sh
    echo -e "${G}  ✓ Ollama installed${N}"
fi

echo -e "${Y}[5/6] Creating directories...${N}"
mkdir -p logs data
echo -e "${G}  ✓ Ready${N}"

echo -e "${Y}[6/6] Permissions...${N}"
chmod +x start.sh
echo -e "${G}  ✓ Done${N}"

echo ""
echo -e "${C}══════════════════════════════════════════════${N}"
echo -e "${G}  ✅ INSTALL COMPLETE!${N}"
echo ""
echo -e "  ${Y}BEFORE STARTING:${N}"
echo -e "  1. Pull your LLM model:  ${C}ollama pull qwen2.5:14b${N}"
echo -e "     (or whatever model you chose)"
echo ""
echo -e "  ${Y}TO START:${N}"
echo -e "  2. Run  ${C}bash start.sh${N}"
echo -e "  3. Open ${C}http://localhost:5050${N}"
echo -e "  4. Click ${C}▶ START${N}"
echo ""
echo -e "  ${Y}TO GO LIVE (after testing):${N}"
echo -e "  Edit ${C}config.yaml${N}:"
echo -e "  - Set ${C}paper_trading: false${N}"
echo -e "  - Add your Kraken API keys"
echo -e "${C}══════════════════════════════════════════════${N}"
