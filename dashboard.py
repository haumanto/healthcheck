#!/usr/bin/env python3
"""
Health Check Dashboard - serves a web UI with interactive graphs.
Reads CSV data produced by healthcheck.py.
Usage: python3 dashboard.py [host] [port]
"""

import json
import csv
import os
import sys
import glob
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"


def load_config():
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    cfg["data_dir"] = str(SCRIPT_DIR / cfg["data_dir"])
    return cfg


def read_data(data_dir, days=1):
    """Read CSV data for the last N days."""
    rows = []
    start = datetime.now() - timedelta(days=days)
    for filepath in sorted(glob.glob(os.path.join(data_dir, "*.csv"))):
        filename = os.path.basename(filepath)
        try:
            file_date = datetime.strptime(filename.replace(".csv", ""), "%Y-%m-%d")
            if file_date < start - timedelta(days=1):
                continue
        except ValueError:
            continue
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    return rows


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Health Check</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #09090b;
    --surface: #0f0f11;
    --surface-hover: #131316;
    --border: rgba(255,255,255,0.04);
    --border-hover: rgba(255,255,255,0.08);
    --text: #e4e4e7;
    --text-secondary: #a1a1aa;
    --text-tertiary: #52525b;
    --green: #34d399;
    --green-soft: rgba(52,211,153,0.1);
    --yellow: #fbbf24;
    --yellow-soft: rgba(251,191,36,0.1);
    --red: #f87171;
    --red-soft: rgba(248,113,113,0.1);
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', ui-monospace, monospace;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: var(--font-sans);
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  .page {
    max-width: 1280px;
    margin: 0 auto;
    padding: 64px 24px 80px;
  }

  @media (min-width: 640px) {
    .page { padding: 64px 32px 80px; }
  }

  @media (min-width: 1024px) {
    .page { padding: 64px 48px 80px; }
  }

  /* Header */
  .header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 64px;
  }

  .header h1 {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text);
  }

  .header .meta {
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-tertiary);
  }

  .live-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .live-dot {
    position: relative;
    display: inline-flex;
    width: 8px;
    height: 8px;
  }

  .live-dot .ping {
    position: absolute;
    display: inline-flex;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: var(--green);
    opacity: 0.4;
    animation: ping 1.5s cubic-bezier(0,0,0.2,1) infinite;
  }

  .live-dot .dot {
    position: relative;
    display: inline-flex;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
  }

  @keyframes ping {
    75%, 100% { transform: scale(2); opacity: 0; }
  }

  .live-label {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.025em;
    color: var(--text-tertiary);
    text-transform: uppercase;
  }

  /* KPIs */
  .kpis {
    display: flex;
    gap: 64px;
    padding-bottom: 40px;
    margin-bottom: 56px;
    border-bottom: 1px solid var(--border);
  }

  @media (max-width: 640px) {
    .kpis { gap: 32px; flex-wrap: wrap; }
  }

  .kpi {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .kpi-label {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.08em;
    color: var(--text-tertiary);
    text-transform: uppercase;
  }

  .kpi-value {
    font-family: var(--font-mono);
    font-size: 28px;
    font-weight: 600;
    line-height: 1;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  .kpi-unit {
    margin-left: 2px;
    font-size: 14px;
    font-weight: 400;
    color: var(--text-tertiary);
  }

  /* Toolbar */
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin-bottom: 40px;
  }

  .toolbar .spacer {
    width: 1px;
    height: 16px;
    background: var(--border);
  }

  .toolbar-label {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.05em;
    color: var(--text-tertiary);
    text-transform: uppercase;
  }

  .seg {
    display: inline-flex;
    overflow: hidden;
    border-radius: 8px;
    border: 1px solid var(--border);
  }

  .seg button {
    background: transparent;
    border: none;
    border-right: 1px solid var(--border);
    padding: 6px 14px;
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 500;
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all 0.12s;
    letter-spacing: 0.01em;
  }

  .seg button:last-child { border-right: none; }
  .seg button:hover { color: var(--text-secondary); background: rgba(255,255,255,0.02); }
  .seg button.active { color: var(--text); background: rgba(255,255,255,0.06); }

  .toolbar input[type="datetime-local"],
  .toolbar select {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border);
    padding: 5px 10px;
    border-radius: 6px;
    font-family: var(--font-sans);
    font-size: 11px;
    outline: none;
    transition: border-color 0.12s;
  }

  .toolbar input:focus, .toolbar select:focus { border-color: var(--border-hover); }
  .toolbar input[type="datetime-local"]::-webkit-calendar-picker-indicator {
    filter: invert(0.5);
    cursor: pointer;
    opacity: 0.5;
    transition: opacity 0.15s;
  }
  .toolbar input[type="datetime-local"]::-webkit-calendar-picker-indicator:hover { opacity: 0.9; }

  .toolbar .ghost {
    background: transparent;
    color: var(--text-tertiary);
    border: none;
    padding: 5px 10px;
    border-radius: 6px;
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.12s;
  }

  .toolbar .ghost:hover { color: var(--text-secondary); }

  .toolbar .end {
    margin-left: auto;
    font-size: 10px;
    letter-spacing: 0.025em;
    color: var(--text-tertiary);
  }

  @media (max-width: 768px) {
    .toolbar .end { margin-left: 0; width: 100%; }
  }

  /* Cards Grid */
  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1px;
    background: var(--border);
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 56px;
  }

  @media (max-width: 640px) {
    .cards-grid { grid-template-columns: 1fr; }
  }

  .card {
    background: var(--surface);
    padding: 24px 28px;
    transition: background 0.15s;
  }

  .card:hover { background: var(--surface-hover); }

  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
  }

  .card-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-sub {
    margin-top: 2px;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-tertiary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pill {
    display: inline-flex;
    flex-shrink: 0;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 999px;
  }

  .pill-ok { color: var(--green); background: var(--green-soft); }
  .pill-degraded { color: var(--yellow); background: var(--yellow-soft); }
  .pill-down { color: var(--red); background: var(--red-soft); }

  .card-body {
    display: flex;
    align-items: flex-end;
    gap: 24px;
    margin-bottom: 4px;
  }

  .card-pct {
    font-family: var(--font-mono);
    font-size: 32px;
    font-weight: 600;
    line-height: 1;
    letter-spacing: -0.03em;
  }

  .card-pct .unit {
    margin-left: 2px;
    font-size: 14px;
    font-weight: 400;
    color: var(--text-tertiary);
  }

  .card-detail {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding-bottom: 4px;
  }

  .card-detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .card-detail-val {
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  .card-spark {
    height: 48px;
    margin-top: 16px;
  }

  /* Panels */
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 28px;
    margin-bottom: 20px;
  }

  .panel-label {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.08em;
    color: var(--text-tertiary);
    text-transform: uppercase;
    margin-bottom: 20px;
  }

  .chart-area {
    position: relative;
    height: 180px;
  }

  /* Heatmap */
  .hm-row {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }

  .hm-name {
    width: 128px;
    flex-shrink: 0;
    font-size: 11px;
    color: var(--text-tertiary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .hm-cells {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }

  .hm-cell {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    cursor: pointer;
    transition: transform 0.1s, opacity 0.1s;
  }

  .hm-cell:hover { transform: scale(1.4); }

  .hm-legend {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 14px;
    padding-left: 128px;
    font-size: 10px;
    color: var(--text-tertiary);
  }

  .hm-legend .sw {
    width: 12px;
    height: 12px;
    border-radius: 3px;
  }

  /* Table */
  .tbl-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
  }

  .tbl-header {
    padding: 20px 28px 0;
  }

  .tbl-scroll {
    max-height: 360px;
    overflow-y: auto;
    padding: 0 28px 20px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th, td {
    text-align: left;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
  }

  th {
    position: sticky;
    top: 0;
    background: var(--surface);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.05em;
    color: var(--text-tertiary);
    text-transform: uppercase;
  }

  td {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .mono {
    font-family: var(--font-mono);
    font-size: 10.5px;
  }

  tr:last-child td { border-bottom: none; }

  tr { transition: background 0.12s; }
  tr:hover { background: rgba(255,255,255,0.02); }

  /* Tooltip */
  .tip {
    display: none;
    position: fixed;
    background: #131316;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 11px;
    color: var(--text);
    z-index: 1000;
    pointer-events: none;
    white-space: nowrap;
    box-shadow: 0 12px 32px rgba(0,0,0,0.6);
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.14); }
</style>
</head>
<body>

<div class="page">

  <header class="header">
    <div>
      <h1>Health Check</h1>
      <p class="meta" id="lastUpdate">Loading...</p>
    </div>
    <div class="live-indicator">
      <span class="live-dot">
        <span class="ping"></span>
        <span class="dot"></span>
      </span>
      <span class="live-label">Live</span>
    </div>
  </header>

  <div class="kpis" id="summary"></div>

  <div class="toolbar">
    <div class="seg">
      <button onclick="setRange(0.0417)" id="btn-1h">1h</button>
      <button onclick="setRange(0.25)" id="btn-6h">6h</button>
      <button class="active" onclick="setRange(1)" id="btn-1d">24h</button>
      <button onclick="setRange(3)" id="btn-3d">3d</button>
      <button onclick="setRange(7)" id="btn-7d">7d</button>
    </div>
    <div class="spacer"></div>
    <label class="toolbar-label">From</label>
    <input type="datetime-local" id="filterFrom" onchange="applyCustomFilter()">
    <label class="toolbar-label">To</label>
    <input type="datetime-local" id="filterTo" onchange="applyCustomFilter()">
    <button class="ghost" onclick="clearCustomFilter()">Reset</button>
    <div class="spacer"></div>
    <select id="filterTarget" onchange="applyTargetFilter()"><option value="">All targets</option></select>
    <select id="filterType" onchange="applyTargetFilter()">
      <option value="">All types</option>
      <option value="tcp">TCP</option>
      <option value="ping">Ping</option>
      <option value="http">HTTP</option>
    </select>
    <span class="end">Auto-refresh 60s</span>
  </div>

  <div class="cards-grid" id="cards"></div>

  <div class="panel">
    <div class="panel-label">Uptime</div>
    <div class="chart-area"><canvas id="uptimeChart"></canvas></div>
  </div>

  <div class="panel">
    <div class="panel-label">Response Time</div>
    <div class="chart-area"><canvas id="latencyChart"></canvas></div>
  </div>

  <div class="panel">
    <div class="panel-label">Availability</div>
    <div id="heatmap"></div>
  </div>

  <div class="tbl-wrap">
    <div class="tbl-header"><div class="panel-label" style="margin-bottom:12px">Event Log</div></div>
    <div class="tbl-scroll">
      <table>
        <thead><tr><th>Time</th><th>Target</th><th>Host</th><th>Type</th><th>Result</th><th>Uptime</th><th>Latency</th><th>HTTP</th><th>State</th></tr></thead>
        <tbody id="logBody"></tbody>
      </table>
    </div>
  </div>

</div>

<div class="tip" id="tooltip"></div>

<script>
const LINE_COLORS = ['#34d399','#60a5fa','#f472b6','#fbbf24','#a78bfa','#22d3ee','#fb923c'];
let currentRange = 1;
let rawData = [];
let allData = [];
let customFilterActive = false;
let uptimeChartInstance = null;
let latencyChartInstance = null;
let cardCharts = {};

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 250 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#131316',
      borderColor: 'rgba(255,255,255,0.06)',
      borderWidth: 1,
      titleColor: '#e4e4e7',
      bodyColor: '#a1a1aa',
      padding: 10,
      cornerRadius: 8,
      displayColors: false,
      titleFont: { weight: '500', family: "'Inter', sans-serif" },
      bodyFont: { family: "'Inter', sans-serif" },
    }
  },
  scales: {
    x: {
      ticks: { color: '#3f3f46', maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 10, family: "'Inter', sans-serif" } },
      grid: { color: 'rgba(255,255,255,0.02)', drawBorder: false },
      border: { display: false },
    },
    y: {
      ticks: { color: '#3f3f46', font: { size: 10, family: "'Inter', sans-serif" } },
      grid: { color: 'rgba(255,255,255,0.02)', drawBorder: false },
      border: { display: false },
    }
  }
};

function setRange(days) {
  currentRange = days;
  customFilterActive = false;
  document.getElementById('filterFrom').value = '';
  document.getElementById('filterTo').value = '';
  document.querySelectorAll('.seg button').forEach(b => b.classList.remove('active'));
  const labels = {0.0417:'1h', 0.25:'6h', 1:'1d', 3:'3d', 7:'7d'};
  const btn = document.getElementById('btn-' + labels[days]);
  if (btn) btn.classList.add('active');
  fetchData();
}

function applyCustomFilter() {
  const from = document.getElementById('filterFrom').value;
  const to = document.getElementById('filterTo').value;
  if (!from && !to) return;
  customFilterActive = true;
  document.querySelectorAll('.seg button').forEach(b => b.classList.remove('active'));
  currentRange = 7;
  fetchData();
}

function clearCustomFilter() {
  customFilterActive = false;
  document.getElementById('filterFrom').value = '';
  document.getElementById('filterTo').value = '';
  document.getElementById('filterTarget').value = '';
  document.getElementById('filterType').value = '';
  setRange(1);
}

function applyTargetFilter() { applyFilters(); render(); }

function applyFilters() {
  let data = [...rawData];
  if (customFilterActive) {
    const from = document.getElementById('filterFrom').value;
    const to = document.getElementById('filterTo').value;
    if (from) { const s = from.replace('T',' ').substring(0,16); data = data.filter(d => d.timestamp >= s); }
    if (to) { const s = to.replace('T',' ').substring(0,16); data = data.filter(d => d.timestamp <= s); }
  }
  const tf = document.getElementById('filterTarget').value;
  if (tf) data = data.filter(d => d.name === tf);
  const yf = document.getElementById('filterType').value;
  if (yf) data = data.filter(d => (d.type||'tcp') === yf);
  allData = data;
}

async function fetchData() {
  try {
    const r = await fetch('/api/data?days=' + currentRange);
    rawData = await r.json();
    const sel = document.getElementById('filterTarget');
    const cv = sel.value;
    const names = [...new Set(rawData.map(d => d.name))].sort();
    sel.innerHTML = '<option value="">All targets</option>' + names.map(n => `<option value="${n}"${n===cv?' selected':''}>${n}</option>`).join('');
    applyFilters();
    render();
  } catch(e) { console.error(e); }
}

function statusOf(p) { return p===100?'ok':p>0?'degraded':'down'; }
function statusColor(p) { return p===100?'#34d399':p>0?'#fbbf24':'#f87171'; }

function groupBy(data) { const m={}; data.forEach(d=>{if(!m[d.name])m[d.name]=[];m[d.name].push(d);}); return m; }

function render() {
  const by = groupBy(allData);
  const names = Object.keys(by).sort();

  const total = names.length;
  const checks = allData.length;
  const pct = checks > 0 ? (allData.reduce((s,r) => s+parseFloat(r.pct),0)/checks).toFixed(1) : 0;
  const lats = allData.filter(r=>r.avg_latency_ms).map(r=>parseFloat(r.avg_latency_ms));
  const avgLat = lats.length ? (lats.reduce((a,b)=>a+b,0)/lats.length).toFixed(1) : '--';

  document.getElementById('summary').innerHTML = `
    <div class="kpi">
      <div class="kpi-label">Targets</div>
      <div class="kpi-value">${total}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Uptime</div>
      <div class="kpi-value" style="color:${statusColor(parseFloat(pct))}">${pct}<span class="kpi-unit">%</span></div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Latency</div>
      <div class="kpi-value">${avgLat}<span class="kpi-unit">ms</span></div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Checks</div>
      <div class="kpi-value">${checks}</div>
    </div>
  `;

  const el = document.getElementById('cards');
  el.innerHTML = '';
  Object.keys(cardCharts).forEach(k => { if(cardCharts[k]) cardCharts[k].destroy(); });
  cardCharts = {};

  names.forEach((name, idx) => {
    const rows = by[name];
    const latest = rows[rows.length-1];
    const cur = parseFloat(latest.pct);
    const avg = (rows.reduce((s,r)=>s+parseFloat(r.pct),0)/rows.length).toFixed(1);
    const st = statusOf(cur);
    const ls = rows.filter(r=>r.avg_latency_ms).map(r=>parseFloat(r.avg_latency_ms));
    const aLat = ls.length ? (ls.reduce((a,b)=>a+b,0)/ls.length).toFixed(1) : '--';

    const cid = 'c'+idx;
    const c = document.createElement('div');
    c.className = 'card';
    c.innerHTML = `
      <div class="card-top">
        <div style="min-width:0">
          <div class="card-name">${name}</div>
          <div class="card-sub">${latest.port?latest.host+':'+latest.port:latest.host} / ${latest.type||'tcp'}</div>
        </div>
        <span class="pill pill-${st}">${st}</span>
      </div>
      <div class="card-body">
        <div class="card-pct" style="color:${statusColor(cur)}">${cur}<span class="unit">%</span></div>
        <div class="card-detail">
          <div class="card-detail-row"><span>avg</span><span class="card-detail-val">${avg}%</span></div>
          <div class="card-detail-row"><span>latency</span><span class="card-detail-val">${aLat}ms</span></div>
        </div>
      </div>
      <div class="card-spark"><canvas id="${cid}"></canvas></div>
    `;
    el.appendChild(c);

    const vals = rows.map(r=>parseFloat(r.pct));
    const labs = rows.map(r=>r.timestamp.split(' ')[1]||r.timestamp);
    const clr = statusColor(cur);

    const ctx = document.getElementById(cid).getContext('2d');
    cardCharts[cid] = new Chart(ctx, {
      type: 'line',
      data: { labels: labs, datasets: [{ data: vals, borderColor: clr, backgroundColor: clr+'08', fill: true, tension: 0.4, pointRadius: 0, pointHitRadius: 6, borderWidth: 1 }] },
      options: { ...chartDefaults, scales: { x:{display:false}, y:{display:false,min:0,max:100} }, plugins: { ...chartDefaults.plugins, tooltip: { ...chartDefaults.plugins.tooltip, callbacks: { label: c=>`${c.parsed.y}%` } } } }
    });
  });

  renderUptime(by, names);
  renderLatency(by, names);
  renderHeat(by, names);
  renderLog();
  document.getElementById('lastUpdate').textContent = new Date().toLocaleString();
}

function renderUptime(by, names) {
  if (uptimeChartInstance) uptimeChartInstance.destroy();
  let labels = [];
  names.forEach(n => { if(by[n].length > labels.length) labels = by[n].map(r=>r.timestamp); });
  const ds = names.map((n,i) => ({ label:n, data:by[n].map(r=>({x:r.timestamp,y:parseFloat(r.pct)})), borderColor:LINE_COLORS[i%LINE_COLORS.length], fill:false, tension:0.4, pointRadius:0, pointHitRadius:6, borderWidth:1.5 }));
  uptimeChartInstance = new Chart(document.getElementById('uptimeChart').getContext('2d'), {
    type:'line', data:{labels,datasets:ds},
    options: { ...chartDefaults,
      plugins: { ...chartDefaults.plugins, legend:{display:true,position:'top',align:'end',labels:{color:'#a1a1aa',boxWidth:6,boxHeight:6,padding:14,font:{size:10,family:"'Inter', sans-serif"},usePointStyle:true,pointStyle:'circle'}}, tooltip:{...chartDefaults.plugins.tooltip,mode:'index',intersect:false,callbacks:{label:c=>` ${c.dataset.label}  ${c.parsed.y}%`}} },
      scales: { ...chartDefaults.scales, y:{...chartDefaults.scales.y,min:0,max:100,ticks:{...chartDefaults.scales.y.ticks,callback:v=>v+'%'}} },
      interaction:{mode:'index',intersect:false}
    }
  });
}

function renderLatency(by, names) {
  if (latencyChartInstance) latencyChartInstance.destroy();
  const has = allData.some(r=>r.avg_latency_ms&&parseFloat(r.avg_latency_ms)>0);
  const el = document.getElementById('latencyChart').parentElement.parentElement;
  if (!has) { el.style.display='none'; return; }
  el.style.display='';
  let labels = [];
  names.forEach(n => { if(by[n].length>labels.length) labels = by[n].map(r=>r.timestamp); });
  const ds = names.map((n,i) => ({ label:n, data:by[n].map(r=>parseFloat(r.avg_latency_ms||0)), borderColor:LINE_COLORS[i%LINE_COLORS.length], fill:false, tension:0.4, pointRadius:0, pointHitRadius:6, borderWidth:1.5 }));
  latencyChartInstance = new Chart(document.getElementById('latencyChart').getContext('2d'), {
    type:'line', data:{labels,datasets:ds},
    options: { ...chartDefaults,
      plugins: { ...chartDefaults.plugins, legend:{display:true,position:'top',align:'end',labels:{color:'#a1a1aa',boxWidth:6,boxHeight:6,padding:14,font:{size:10,family:"'Inter', sans-serif"},usePointStyle:true,pointStyle:'circle'}}, tooltip:{...chartDefaults.plugins.tooltip,mode:'index',intersect:false,callbacks:{label:c=>` ${c.dataset.label}  ${c.parsed.y.toFixed(1)}ms`}} },
      scales: { ...chartDefaults.scales, y:{...chartDefaults.scales.y,min:0,ticks:{...chartDefaults.scales.y.ticks,callback:v=>v+'ms'}} },
      interaction:{mode:'index',intersect:false}
    }
  });
}

function renderHeat(by, names) {
  const box = document.getElementById('heatmap');
  box.innerHTML = '';
  const tip = document.getElementById('tooltip');
  names.forEach(name => {
    const rows = by[name];
    const hourly = {};
    rows.forEach(r => { const h=r.timestamp.substring(0,13); if(!hourly[h])hourly[h]=[]; hourly[h].push(parseFloat(r.pct)); });
    const row = document.createElement('div'); row.className='hm-row';
    const lbl = document.createElement('div'); lbl.className='hm-name'; lbl.textContent=name; row.appendChild(lbl);
    const wrap = document.createElement('div'); wrap.className='hm-cells';
    Object.keys(hourly).sort().forEach(h => {
      const vs=hourly[h]; const avg=vs.reduce((a,b)=>a+b,0)/vs.length;
      const c=document.createElement('div'); c.className='hm-cell'; c.style.backgroundColor=heatColor(avg);
      c.addEventListener('mouseenter',e=>{tip.style.display='block';tip.textContent=`${h}:00  ${avg.toFixed(1)}%  (${vs.length})`;tip.style.left=e.clientX+12+'px';tip.style.top=e.clientY-36+'px';});
      c.addEventListener('mouseleave',()=>{tip.style.display='none';});
      wrap.appendChild(c);
    });
    row.appendChild(wrap); box.appendChild(row);
  });
  const leg=document.createElement('div'); leg.className='hm-legend';
  leg.innerHTML='<span>0%</span>';
  [0,25,50,75,100].forEach(v=>{leg.innerHTML+=`<div class="sw" style="background:${heatColor(v)}"></div>`;});
  leg.innerHTML+='<span>100%</span>'; box.appendChild(leg);
}

function heatColor(p) {
  if(p>=99.5) return 'rgba(52,211,153,0.6)';
  if(p>=95) return 'rgba(52,211,153,0.4)';
  if(p>=80) return 'rgba(52,211,153,0.2)';
  if(p>=50) return 'rgba(251,191,36,0.35)';
  if(p>=20) return 'rgba(251,191,36,0.2)';
  if(p>0) return 'rgba(248,113,113,0.4)';
  return 'rgba(248,113,113,0.15)';
}

function renderLog() {
  const b=document.getElementById('logBody');
  const rec=allData.slice(-80).reverse();
  b.innerHTML=rec.map(r=>{
    const p=parseFloat(r.pct); const st=statusOf(p);
    const lat=r.avg_latency_ms?parseFloat(r.avg_latency_ms).toFixed(1)+'ms':'--';
    const host=r.port?r.host+':'+r.port:r.host;
    const http=r.http_status||'--';
    return `<tr>
      <td class="mono">${r.timestamp}</td>
      <td>${r.name}</td>
      <td class="mono">${host}</td>
      <td>${r.type||'tcp'}</td>
      <td class="mono">${r.successes}/${r.checks}</td>
      <td class="mono">${r.pct}%</td>
      <td class="mono">${lat}</td>
      <td class="mono">${http}</td>
      <td><span class="pill pill-${st}">${st}</span></td>
    </tr>`;
  }).join('');
}

fetchData();
setInterval(fetchData, 60000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    config = None

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())

        elif parsed.path == "/api/data":
            params = parse_qs(parsed.query)
            days = float(params.get("days", [1])[0])
            data = read_data(self.config["data_dir"], days)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        elif parsed.path == "/api/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(self.config).encode())

        else:
            self.send_response(404)
            self.end_headers()


def main():
    config = load_config()
    Handler.config = config

    host = sys.argv[1] if len(sys.argv) > 1 else config.get("dashboard_host", "0.0.0.0")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else config.get("dashboard_port", 8111)

    server = HTTPServer((host, port), Handler)
    print(f"Dashboard running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
