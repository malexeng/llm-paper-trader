#!/usr/bin/env bash

set -e  # Stop on error

echo ""
echo "═══════════════════════════════════════════════════════"
echo "   LLM PAPER TRADER - FULL AUTOMATIC SETUP"
echo "═══════════════════════════════════════════════════════"
echo ""

# Install missing Python packages
echo "[1/4] Installing Python dependencies..."
source venv/bin/activate 2>/dev/null || python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet flask ccxt pandas numpy requests python-dotenv websocket-client pyyaml

# Verify installations
echo "[2/4] Verifying installations..."
python3 -c "import flask; import ccxt; import pandas; print('✅ All packages installed')" || {
    echo "❌ Installation failed, retrying..."
    pip install flask ccxt pandas numpy requests python-dotenv websocket-client pyyaml
}

# Check Ollama
echo "[3/4] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "📦 Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
fi

# Pull model if needed
if ! ollama list 2>/dev/null | grep -q "qwen2.5:14b"; then
    echo "📥 Pulling AI model (this takes ~5 minutes)..."
    ollama pull qwen2.5:14b &
    MODEL_PID=$!
    echo "Pulling in background..."
fi

# Create default config if missing
echo "[4/4] Creating configuration..."
cat > config.yaml << 'EOF'
exchange:
  name: kraken
  api_key: ""
  api_secret: ""
  paper_trading: true
  sandbox_mode: true

llm_provider: ollama
llm_model: qwen2.5:14b
llm_host: http://localhost:11434
llm_timeout: 30

pairs:
  - BTC/USDT
  - ETH/USDT

analysis_interval_secs: 30
risk_per_trade_pct: 2.0
max_position_usdc: 100
rsi_period: 14
macd_fast: 12
macd_slow: 26
macd_signal: 9
bb_period: 20
bb_std: 2.0

host: 0.0.0.0
port: 5050
log_level: INFO
EOF

# Create dashboard if missing
if [ ! -f "dashboard/app.py" ]; then
    mkdir -p dashboard/templates
    mkdir -p dashboard/static/css
    mkdir -p dashboard/static/js
    
    # Create dashboard app
    cat > dashboard/app.py << 'DASHBOARD'
from flask import Flask, render_template, jsonify, request
import time
import threading
from datetime import datetime

def create_app(state):
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return render_template('dashboard.html')
    
    @app.route('/api/status')
    def status():
        return jsonify({
            'running': state.get('running', False),
            'paused': state.get('paused', False),
            'llm_status': state.get('llm_status', 'unknown'),
            'stats': state.get('stats', {}),
            'positions': state.get('positions', []),
            'prices': state.get('prices', {}),
            'reasoning': state.get('reasoning', [])[-5:],
            'uptime': int(time.time() - state.get('uptime_start', time.time()))
        })
    
    @app.route('/api/control', methods=['POST'])
    def control():
        action = request.json.get('action')
        if action == 'start':
            state['start_signal'] = True
        elif action == 'stop':
            state['stop_signal'] = True
        elif action == 'pause':
            state['pause_signal'] = True
        elif action == 'resume':
            state['resume_signal'] = True
        return jsonify({'status': 'ok'})
    
    return app
DASHBOARD

    # Create HTML dashboard
    cat > dashboard/templates/dashboard.html << 'HTML'
<!DOCTYPE html>
<html>
<head>
    <title>LLM Paper Trader - AI Trading Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
        }
        .status-bar {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .status-card {
            background: white;
            border-radius: 10px;
            padding: 15px;
            flex: 1;
            min-width: 150px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .status-card h3 {
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }
        .status-card .value {
            font-size: 24px;
            font-weight: bold;
        }
        .running { color: #10b981; }
        .stopped { color: #ef4444; }
        .paused { color: #f59e0b; }
        
        .controls {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        button {
            padding: 10px 20px;
            font-size: 14px;
            font-weight: bold;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover { transform: translateY(-2px); }
        .btn-start { background: #10b981; color: white; }
        .btn-stop { background: #ef4444; color: white; }
        .btn-pause { background: #f59e0b; color: white; }
        .btn-resume { background: #3b82f6; color: white; }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .card h2 {
            margin-bottom: 15px;
            font-size: 18px;
            color: #333;
        }
        table {
            width: 100%;
            font-size: 12px;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        .reasoning-log {
            max-height: 300px;
            overflow-y: auto;
            font-size: 12px;
        }
        .log-entry {
            padding: 8px;
            margin-bottom: 5px;
            background: #f8f9fa;
            border-left: 3px solid #667eea;
            border-radius: 3px;
        }
        .price-up { color: #10b981; }
        .price-down { color: #ef4444; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .live-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #10b981;
            margin-right: 5px;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 LLM Paper Trader - AI Crypto Trading Agent</h1>
            <p>Powered by Qwen2.5 14B | Paper Trading Mode</p>
        </div>
        
        <div class="status-bar" id="statusBar">
            <div class="status-card">
                <h3>Bot Status</h3>
                <div class="value" id="botStatus">Loading...</div>
            </div>
            <div class="status-card">
                <h3>LLM Status</h3>
                <div class="value" id="llmStatus">Loading...</div>
            </div>
            <div class="status-card">
                <h3>Uptime</h3>
                <div class="value" id="uptime">0s</div>
            </div>
            <div class="status-card">
                <h3>Total P&L</h3>
                <div class="value" id="pnl">$0</div>
            </div>
            <div class="status-card">
                <h3>Win Rate</h3>
                <div class="value" id="winRate">0%</div>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn-start" onclick="control('start')">▶ START BOT</button>
            <button class="btn-stop" onclick="control('stop')">⏹ STOP BOT</button>
            <button class="btn-pause" onclick="control('pause')">⏸ PAUSE</button>
            <button class="btn-resume" onclick="control('resume')">▶ RESUME</button>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>📊 Open Positions</h2>
                <div id="positions">
                    <p style="color: #999;">No open positions</p>
                </div>
            </div>
            
            <div class="card">
                <h2>💰 Live Prices</h2>
                <div id="prices">
                    <p style="color: #999;">Loading prices...</p>
                </div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>📈 Trade History</h2>
                <div id="history">
                    <p style="color: #999;">No trades yet</p>
                </div>
            </div>
            
            <div class="card">
                <h2>🧠 AI Reasoning Log</h2>
                <div id="reasoning" class="reasoning-log">
                    <p style="color: #999;">Waiting for AI analysis...</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update status
                const botStatus = document.getElementById('botStatus');
                if (data.running) {
                    botStatus.innerHTML = '<span class="live-indicator"></span>RUNNING';
                    botStatus.className = 'value running';
                } else if (data.paused) {
                    botStatus.innerHTML = 'PAUSED';
                    botStatus.className = 'value paused';
                } else {
                    botStatus.innerHTML = 'STOPPED';
                    botStatus.className = 'value stopped';
                }
                
                document.getElementById('llmStatus').innerHTML = data.llm_status.toUpperCase();
                document.getElementById('uptime').innerHTML = formatUptime(data.uptime);
                document.getElementById('pnl').innerHTML = `$${data.stats.total_pnl?.toFixed(2) || '0'}`;
                document.getElementById('winRate').innerHTML = `${data.stats.win_rate?.toFixed(1) || '0'}%`;
                
                // Update positions
                if (data.positions && data.positions.length > 0) {
                    let html = '<table><tr><th>Pair</th><th>Side</th><th>Size</th><th>Entry</th><th>Current</th><th>P&L</th></tr>';
                    data.positions.forEach(pos => {
                        const currentPrice = data.prices[pos.pair]?.price || pos.entry_price;
                        const pnl = pos.side === 'long' ? 
                            (currentPrice - pos.entry_price) / pos.entry_price * 100 :
                            (pos.entry_price - currentPrice) / pos.entry_price * 100;
                        html += `<tr>
                            <td>${pos.pair}</td>
                            <td>${pos.side.toUpperCase()}</td>
                            <td>$${pos.size_usdc}</td>
                            <td>$${pos.entry_price}</td>
                            <td>$${currentPrice.toFixed(2)}</td>
                            <td class="${pnl >= 0 ? 'price-up' : 'price-down'}">${pnl.toFixed(2)}%</td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('positions').innerHTML = html;
                } else {
                    document.getElementById('positions').innerHTML = '<p style="color: #999;">No open positions</p>';
                }
                
                // Update prices
                if (Object.keys(data.prices).length > 0) {
                    let html = '<table><tr><th>Pair</th><th>Price</th><th>Updated</th></tr>';
                    for (const [pair, info] of Object.entries(data.prices)) {
                        html += `<tr>
                            <td>${pair}</td>
                            <td>$${info.price.toFixed(2)}</td>
                            <td>${new Date(info.ts).toLocaleTimeString()}</td>
                        </tr>`;
                    }
                    html += '</table>';
                    document.getElementById('prices').innerHTML = html;
                } else {
                    document.getElementById('prices').innerHTML = '<p style="color: #999;">Waiting for market data...</p>';
                }
                
                // Update reasoning
                if (data.reasoning && data.reasoning.length > 0) {
                    let html = '';
                    data.reasoning.slice().reverse().forEach(log => {
                        html += `<div class="log-entry">
                            <strong>${log.timestamp || 'Just now'}</strong><br>
                            ${log.message || log}
                        </div>`;
                    });
                    document.getElementById('reasoning').innerHTML = html;
                }
                
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }
        
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            return `${hours}h ${minutes}m ${secs}s`;
        }
        
        async function control(action) {
            try {
                await fetch('/api/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: action})
                });
                setTimeout(fetchStatus, 500);
            } catch (error) {
                console.error('Control error:', error);
            }
        }
        
        setInterval(fetchStatus, 2000);
        fetchStatus();
    </script>
</body>
</html>
HTML
fi

# Wait for model if it's still pulling
if [ -n "$MODEL_PID" ] && ps -p $MODEL_PID > /dev/null; then
    echo "⏳ Waiting for model download to complete..."
    wait $MODEL_PID
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ SETUP COMPLETE!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Starting LLM Paper Trader with Dashboard..."
echo ""

# Start the bot
source venv/bin/activate
python3 main.py &

# Wait for bot to start
sleep 3

# Open dashboard in browser
echo ""
echo "🌐 Opening dashboard in your browser..."
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5050
elif command -v open &> /dev/null; then
    open http://localhost:5050
else
    echo "   Please open: http://localhost:5050"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Dashboard: http://localhost:5050"
echo "  Stop bot:  Press Ctrl+C"
echo "═══════════════════════════════════════════════════════"
echo ""

# Keep running
wait
