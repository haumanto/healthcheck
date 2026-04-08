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
<title>Health Check Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #09090b;
    --card: #131316;
    --card-hover: #18181c;
    --border: rgba(255,255,255,0.06);
    --text: #ececef;
    --text-secondary: #a0a0ab;
    --dim: #63637a;
    --green: #22c55e;
    --green-muted: rgba(34,197,94,0.12);
    --yellow: #eab308;
    --yellow-muted: rgba(234,179,8,0.12);
    --red: #ef4444;
    --red-muted: rgba(239,68,68,0.12);
    --accent: #7c7c8a;
    --ring: rgba(255,255,255,0.08);
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 0 0 1px var(--border);
    --shadow-lg: 0 4px 12px rgba(0,0,0,0.4), 0 0 0 1px var(--border);
    --mono: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 32px 40px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }

  .container { max-width: 1400px; margin: 0 auto; }

  /* Typography */
  h1 {
    font-size: 1.5em;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--text);
    margin-bottom: 4px;
  }
  h2 {
    font-size: 0.75em;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--dim);
    margin-bottom: 16px;
  }
  .subtitle {
    color: var(--dim);
    font-size: 0.8em;
    margin-bottom: 32px;
  }

  /* Summary bar */
  .summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 32px;
  }
  .summary-item {
    background: var(--card);
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: var(--shadow);
    transition: box-shadow 0.15s ease;
  }
  .summary-item:hover { box-shadow: var(--shadow-lg); }
  .summary-label {
    font-size: 0.7em;
    font-weight: 500;
    color: var(--dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
  }
  .summary-value {
    font-size: 2em;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--text-secondary);
  }

  /* Toolbar */
  .toolbar {
    background: var(--card);
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: var(--shadow);
    margin-bottom: 32px;
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
  }
  .toolbar-group {
    display: flex;
    align-items: center;
    gap: 0;
  }
  .toolbar-group .tbtn {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border);
    padding: 7px 14px;
    font-size: 0.78em;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    border-right: none;
    letter-spacing: 0.01em;
  }
  .toolbar-group .tbtn:first-child { border-radius: 8px 0 0 8px; }
  .toolbar-group .tbtn:last-child { border-radius: 0 8px 8px 0; border-right: 1px solid var(--border); }
  .toolbar-group .tbtn:hover { background: rgba(255,255,255,0.04); color: var(--text); }
  .toolbar-group .tbtn.active {
    background: rgba(255,255,255,0.08);
    color: var(--text);
    border-color: rgba(255,255,255,0.12);
  }
  .toolbar-divider { width: 1px; height: 24px; background: var(--border); margin: 0 4px; flex-shrink: 0; }
  .toolbar-label { font-size: 0.72em; color: var(--dim); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500; }
  .toolbar input[type="datetime-local"],
  .toolbar select {
    background: rgba(255,255,255,0.04);
    color: var(--text-secondary);
    border: 1px solid var(--border);
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 0.78em;
    cursor: pointer;
    transition: all 0.15s ease;
    outline: none;
  }
  .toolbar input[type="datetime-local"]:hover,
  .toolbar select:hover {
    background: rgba(255,255,255,0.06);
    border-color: rgba(255,255,255,0.12);
  }
  .toolbar input[type="datetime-local"]:focus,
  .toolbar select:focus {
    border-color: rgba(255,255,255,0.2);
  }
  .toolbar input[type="datetime-local"]::-webkit-calendar-picker-indicator { filter: invert(0.5); }
  .toolbar .clear-btn {
    background: transparent;
    color: var(--dim);
    border: 1px solid var(--border);
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.78em;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .toolbar .clear-btn:hover { background: rgba(255,255,255,0.04); color: var(--text-secondary); }
  .refresh-info { color: var(--dim); font-size: 0.7em; margin-left: auto; }

  /* Target cards grid */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 16px;
    margin-bottom: 40px;
  }
  .card {
    background: var(--card);
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: var(--shadow);
    transition: all 0.2s ease;
  }
  .card:hover {
    box-shadow: var(--shadow-lg);
    transform: translateY(-1px);
    background: var(--card-hover);
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
  }
  .card-title { font-size: 0.9em; font-weight: 500; color: var(--text); }
  .card-host { font-size: 0.72em; color: var(--dim); margin-top: 2px; font-family: var(--mono); }
  .badge {
    padding: 3px 10px;
    border-radius: 100px;
    font-size: 0.68em;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    flex-shrink: 0;
  }
  .badge-ok { background: var(--green-muted); color: var(--green); }
  .badge-degraded { background: var(--yellow-muted); color: var(--yellow); }
  .badge-down { background: var(--red-muted); color: var(--red); }

  .card-metrics { display: flex; align-items: center; gap: 20px; margin-bottom: 16px; }
  .gauge-wrap { position: relative; width: 72px; height: 72px; flex-shrink: 0; }
  .gauge-wrap canvas { width: 72px; height: 72px; }
  .gauge-label {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 1em;
    font-weight: 600;
    font-family: var(--mono);
  }
  .metric-stats { display: flex; flex-direction: column; gap: 6px; font-size: 0.78em; color: var(--dim); flex: 1; }
  .metric-stats span { display: flex; justify-content: space-between; }
  .metric-stats .val { color: var(--text-secondary); font-weight: 500; font-family: var(--mono); font-size: 0.95em; }

  .chart-container { position: relative; height: 100px; margin-top: 4px; }

  /* Full-width chart sections */
  .section {
    background: var(--card);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: var(--shadow);
  }
  .section .chart-wide { position: relative; height: 200px; }

  /* Heatmap */
  .heatmap { margin-top: 4px; }
  .heatmap-row { display: flex; align-items: center; margin-bottom: 6px; }
  .heatmap-label {
    width: 140px;
    font-size: 0.75em;
    color: var(--dim);
    flex-shrink: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding-right: 12px;
  }
  .heatmap-cells { display: flex; gap: 3px; flex-wrap: wrap; flex: 1; }
  .heatmap-cell {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    cursor: pointer;
    transition: transform 0.1s ease;
  }
  .heatmap-cell:hover { transform: scale(1.3); }
  .heatmap-legend {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 12px;
    padding-left: 140px;
    font-size: 0.68em;
    color: var(--dim);
  }
  .heatmap-legend .swatch { width: 14px; height: 14px; border-radius: 3px; }
  .tooltip {
    display: none;
    position: fixed;
    background: var(--card);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.75em;
    color: var(--text);
    z-index: 1000;
    pointer-events: none;
    white-space: nowrap;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    backdrop-filter: blur(8px);
  }

  /* Log table */
  .table-card {
    background: var(--card);
    border-radius: 12px;
    padding: 24px;
    overflow-x: auto;
    box-shadow: var(--shadow);
  }
  table { width: 100%; border-collapse: collapse; font-size: 0.78em; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
  th {
    color: var(--dim);
    font-weight: 500;
    font-size: 0.9em;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    position: sticky;
    top: 0;
    background: var(--card);
  }
  td { color: var(--text-secondary); }
  td:nth-child(5), td:nth-child(6), td:nth-child(7), td:nth-child(8) {
    font-family: var(--mono);
    font-size: 0.95em;
  }
  tr:hover td { background: rgba(255,255,255,0.02); }
  .scroll-table { max-height: 380px; overflow-y: auto; }

  @media (max-width: 768px) {
    body { padding: 16px; }
    .grid { grid-template-columns: 1fr; }
    .summary { grid-template-columns: repeat(2, 1fr); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .toolbar-group { flex-wrap: wrap; }
    .refresh-info { margin-left: 0; }
  }
</style>
</head>
<body>

<div class="container">

<h1>Health Check Dashboard</h1>
<div class="subtitle" id="lastUpdate">Loading...</div>

<!-- Summary -->
<div class="summary" id="summary"></div>

<!-- Toolbar -->
<div class="toolbar">
  <div class="toolbar-group">
    <button class="tbtn" onclick="setRange(0.0417)" id="btn-1h">1H</button>
    <button class="tbtn" onclick="setRange(0.25)" id="btn-6h">6H</button>
    <button class="tbtn active" onclick="setRange(1)" id="btn-1d">1D</button>
    <button class="tbtn" onclick="setRange(3)" id="btn-3d">3D</button>
    <button class="tbtn" onclick="setRange(7)" id="btn-7d">7D</button>
  </div>
  <div class="toolbar-divider"></div>
  <span class="toolbar-label">From</span>
  <input type="datetime-local" id="filterFrom" onchange="applyCustomFilter()">
  <span class="toolbar-label">To</span>
  <input type="datetime-local" id="filterTo" onchange="applyCustomFilter()">
  <button class="clear-btn" onclick="clearCustomFilter()">Clear</button>
  <div class="toolbar-divider"></div>
  <select id="filterTarget" onchange="applyTargetFilter()">
    <option value="">All Targets</option>
  </select>
  <select id="filterType" onchange="applyTargetFilter()">
    <option value="">All Types</option>
    <option value="tcp">TCP</option>
    <option value="ping">Ping</option>
    <option value="http">HTTP</option>
  </select>
  <span class="refresh-info">Auto-refresh 60s</span>
</div>

<!-- Per-target cards -->
<div class="grid" id="cards"></div>

<!-- Combined uptime graph -->
<div class="section">
  <h2>Uptime Overview</h2>
  <div class="chart-wide"><canvas id="uptimeChart"></canvas></div>
</div>

<!-- Latency graph -->
<div class="section">
  <h2>Latency</h2>
  <div class="chart-wide"><canvas id="latencyChart"></canvas></div>
</div>

<!-- Heatmap -->
<div class="section">
  <h2>Availability Heatmap</h2>
  <div id="heatmap" class="heatmap"></div>
</div>

<!-- Log table -->
<div class="table-card">
  <h2>Recent Checks</h2>
  <div class="scroll-table">
    <table>
      <thead><tr><th>Time</th><th>Target</th><th>Host</th><th>Type</th><th>Success</th><th>%</th><th>Latency</th><th>HTTP</th><th>Status</th></tr></thead>
      <tbody id="logBody"></tbody>
    </table>
  </div>
</div>

</div><!-- /container -->

<div class="tooltip" id="tooltip"></div>

<script>
const COLORS = ['#22c55e','#4ade80','#86efac','#a3e635','#a1a1aa','#71717a','#d4d4d8'];
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
  animation: { duration: 300 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#131316',
      borderColor: 'rgba(255,255,255,0.1)',
      borderWidth: 1,
      titleColor: '#ececef',
      bodyColor: '#a0a0ab',
      padding: 10,
      cornerRadius: 8,
      displayColors: true,
      boxPadding: 4,
    }
  },
  scales: {
    x: {
      ticks: { color: '#63637a', maxRotation: 0, autoSkip: true, maxTicksLimit: 10, font: { size: 10 } },
      grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
      border: { display: false },
    },
    y: {
      ticks: { color: '#63637a', font: { size: 10 } },
      grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
      border: { display: false },
    }
  }
};

function setRange(days) {
  currentRange = days;
  customFilterActive = false;
  document.getElementById('filterFrom').value = '';
  document.getElementById('filterTo').value = '';
  document.querySelectorAll('.toolbar-group .tbtn').forEach(b => b.classList.remove('active'));
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
  document.querySelectorAll('.toolbar-group .tbtn').forEach(b => b.classList.remove('active'));
  const days = 7;
  currentRange = days;
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

function applyTargetFilter() {
  applyFilters();
  render();
}

function applyFilters() {
  let data = [...rawData];

  if (customFilterActive) {
    const from = document.getElementById('filterFrom').value;
    const to = document.getElementById('filterTo').value;
    if (from) {
      const fromStr = from.replace('T', ' ').substring(0, 16);
      data = data.filter(d => d.timestamp >= fromStr);
    }
    if (to) {
      const toStr = to.replace('T', ' ').substring(0, 16);
      data = data.filter(d => d.timestamp <= toStr);
    }
  }

  const targetFilter = document.getElementById('filterTarget').value;
  if (targetFilter) data = data.filter(d => d.name === targetFilter);

  const typeFilter = document.getElementById('filterType').value;
  if (typeFilter) data = data.filter(d => (d.type || 'tcp') === typeFilter);

  allData = data;
}

async function fetchData() {
  try {
    const r = await fetch('/api/data?days=' + currentRange);
    rawData = await r.json();
    const targetSelect = document.getElementById('filterTarget');
    const currentVal = targetSelect.value;
    const names = [...new Set(rawData.map(d => d.name))].sort();
    targetSelect.innerHTML = '<option value="">All Targets</option>' +
      names.map(n => `<option value="${n}"${n===currentVal?' selected':''}>${n}</option>`).join('');
    applyFilters();
    render();
  } catch(e) { console.error(e); }
}

function statusOf(pct) {
  return pct === 100 ? 'ok' : pct > 0 ? 'degraded' : 'down';
}

function statusColor(pct) {
  return pct === 100 ? '#22c55e' : pct > 0 ? '#eab308' : '#ef4444';
}

function drawGauge(canvas, pct) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  canvas.width = 72 * dpr;
  canvas.height = 72 * dpr;
  ctx.scale(dpr, dpr);
  const cx = 36, cy = 36, r = 28, lw = 5;
  const startAngle = 0.75 * Math.PI;
  const totalAngle = 1.5 * Math.PI;

  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, startAngle + totalAngle);
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = lw;
  ctx.lineCap = 'round';
  ctx.stroke();

  if (pct > 0) {
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, startAngle + totalAngle * (pct / 100));
    ctx.strokeStyle = statusColor(pct);
    ctx.lineWidth = lw;
    ctx.lineCap = 'round';
    ctx.stroke();
  }
}

function groupByTarget(data) {
  const m = {};
  data.forEach(d => {
    if (!m[d.name]) m[d.name] = [];
    m[d.name].push(d);
  });
  return m;
}

function render() {
  const byTarget = groupByTarget(allData);
  const targetNames = Object.keys(byTarget).sort();

  // Summary
  const totalTargets = targetNames.length;
  const totalChecks = allData.length;
  const overallPct = totalChecks > 0
    ? (allData.reduce((s, r) => s + parseFloat(r.pct), 0) / totalChecks).toFixed(1)
    : 0;
  const latencies = allData.filter(r => r.avg_latency_ms).map(r => parseFloat(r.avg_latency_ms));
  const avgLat = latencies.length ? (latencies.reduce((a,b) => a+b, 0) / latencies.length).toFixed(1) : '--';

  document.getElementById('summary').innerHTML = `
    <div class="summary-item"><div class="summary-label">Targets</div><div class="summary-value">${totalTargets}</div></div>
    <div class="summary-item"><div class="summary-label">Overall Uptime</div><div class="summary-value" style="color:${statusColor(parseFloat(overallPct))}">${overallPct}%</div></div>
    <div class="summary-item"><div class="summary-label">Avg Latency</div><div class="summary-value">${avgLat}<span style="font-size:0.5em;color:var(--dim)">ms</span></div></div>
    <div class="summary-item"><div class="summary-label">Data Points</div><div class="summary-value">${totalChecks}</div></div>
  `;

  // Per-target cards
  const cardsEl = document.getElementById('cards');
  cardsEl.innerHTML = '';
  Object.keys(cardCharts).forEach(k => { if (cardCharts[k]) cardCharts[k].destroy(); });
  cardCharts = {};

  targetNames.forEach((name, idx) => {
    const rows = byTarget[name];
    const latest = rows[rows.length - 1];
    const avgPct = (rows.reduce((s, r) => s + parseFloat(r.pct), 0) / rows.length).toFixed(1);
    const minPct = Math.min(...rows.map(r => parseFloat(r.pct))).toFixed(1);
    const curPct = parseFloat(latest.pct);
    const status = statusOf(curPct);
    const lats = rows.filter(r => r.avg_latency_ms).map(r => parseFloat(r.avg_latency_ms));
    const cardAvgLat = lats.length ? (lats.reduce((a,b)=>a+b,0)/lats.length).toFixed(1) : '--';
    const cardMinLat = lats.length ? Math.min(...lats).toFixed(1) : '--';
    const cardMaxLat = lats.length ? Math.max(...lats).toFixed(1) : '--';

    const cardId = 'card-' + idx;
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="card-header">
        <div>
          <div class="card-title">${name}</div>
          <div class="card-host">${latest.port ? latest.host+':'+latest.port : latest.host} ${latest.type || 'tcp'}</div>
        </div>
        <span class="badge badge-${status}">${status.charAt(0).toUpperCase()+status.slice(1)}</span>
      </div>
      <div class="card-metrics">
        <div class="gauge-wrap"><canvas id="gauge-${idx}"></canvas><div class="gauge-label" style="color:${statusColor(curPct)}">${curPct}%</div></div>
        <div class="metric-stats">
          <span>Avg uptime <span class="val">${avgPct}%</span></span>
          <span>Min uptime <span class="val">${minPct}%</span></span>
          <span>Avg latency <span class="val">${cardAvgLat}ms</span></span>
          <span>Min / Max <span class="val">${cardMinLat} / ${cardMaxLat}ms</span></span>
        </div>
      </div>
      <div class="chart-container"><canvas id="${cardId}"></canvas></div>
    `;
    cardsEl.appendChild(card);

    drawGauge(document.getElementById('gauge-' + idx), curPct);

    const labels = rows.map(r => r.timestamp.split(' ')[1] || r.timestamp);
    const values = rows.map(r => parseFloat(r.pct));
    const lineColor = statusColor(curPct);

    const ctx = document.getElementById(cardId).getContext('2d');
    cardCharts[cardId] = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: lineColor,
          backgroundColor: lineColor + '10',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHitRadius: 8,
          borderWidth: 1.5,
        }]
      },
      options: {
        ...chartDefaults,
        scales: {
          x: { ...chartDefaults.scales.x, display: false },
          y: { ...chartDefaults.scales.y, display: false, min: 0, max: 100 }
        },
        plugins: {
          ...chartDefaults.plugins,
          tooltip: {
            ...chartDefaults.plugins.tooltip,
            callbacks: { label: ctx => `Uptime: ${ctx.parsed.y}%` }
          }
        }
      }
    });
  });

  renderUptimeChart(byTarget, targetNames);
  renderLatencyChart(byTarget, targetNames);
  renderHeatmap(byTarget, targetNames);
  renderLog();

  document.getElementById('lastUpdate').textContent =
    'Last updated: ' + new Date().toLocaleString();
}

function renderUptimeChart(byTarget, names) {
  if (uptimeChartInstance) uptimeChartInstance.destroy();
  const datasets = names.map((name, i) => {
    const rows = byTarget[name];
    return {
      label: name,
      data: rows.map(r => ({ x: r.timestamp, y: parseFloat(r.pct) })),
      borderColor: COLORS[i % COLORS.length],
      backgroundColor: COLORS[i % COLORS.length] + '08',
      fill: false,
      tension: 0.4,
      pointRadius: 0,
      pointHitRadius: 8,
      borderWidth: 1.5,
    };
  });

  let labels = [];
  names.forEach(n => { if (byTarget[n].length > labels.length) labels = byTarget[n].map(r => r.timestamp); });

  const ctx = document.getElementById('uptimeChart').getContext('2d');
  uptimeChartInstance = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      ...chartDefaults,
      plugins: {
        ...chartDefaults.plugins,
        legend: { display: true, position: 'top', align: 'end', labels: { color: '#63637a', boxWidth: 8, boxHeight: 8, padding: 16, font: { size: 11 }, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: { ...chartDefaults.plugins.tooltip, mode: 'index', intersect: false, callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y}%` } }
      },
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y, min: 0, max: 100, ticks: { ...chartDefaults.scales.y.ticks, callback: v => v + '%' } }
      },
      interaction: { mode: 'index', intersect: false }
    }
  });
}

function renderLatencyChart(byTarget, names) {
  if (latencyChartInstance) latencyChartInstance.destroy();

  const hasLatency = allData.some(r => r.avg_latency_ms && parseFloat(r.avg_latency_ms) > 0);
  if (!hasLatency) {
    document.getElementById('latencyChart').parentElement.parentElement.style.display = 'none';
    return;
  }
  document.getElementById('latencyChart').parentElement.parentElement.style.display = '';

  let labels = [];
  names.forEach(n => { if (byTarget[n].length > labels.length) labels = byTarget[n].map(r => r.timestamp); });

  const datasets = names.map((name, i) => {
    const rows = byTarget[name];
    return {
      label: name,
      data: rows.map(r => parseFloat(r.avg_latency_ms || 0)),
      borderColor: COLORS[i % COLORS.length],
      fill: false,
      tension: 0.4,
      pointRadius: 0,
      pointHitRadius: 8,
      borderWidth: 1.5,
    };
  });

  const ctx = document.getElementById('latencyChart').getContext('2d');
  latencyChartInstance = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      ...chartDefaults,
      plugins: {
        ...chartDefaults.plugins,
        legend: { display: true, position: 'top', align: 'end', labels: { color: '#63637a', boxWidth: 8, boxHeight: 8, padding: 16, font: { size: 11 }, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: { ...chartDefaults.plugins.tooltip, mode: 'index', intersect: false, callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}ms` } }
      },
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y, min: 0, ticks: { ...chartDefaults.scales.y.ticks, callback: v => v + 'ms' } }
      },
      interaction: { mode: 'index', intersect: false }
    }
  });
}

function renderHeatmap(byTarget, names) {
  const container = document.getElementById('heatmap');
  container.innerHTML = '';
  const tooltip = document.getElementById('tooltip');

  names.forEach(name => {
    const rows = byTarget[name];
    const hourly = {};
    rows.forEach(r => {
      const h = r.timestamp.substring(0, 13);
      if (!hourly[h]) hourly[h] = [];
      hourly[h].push(parseFloat(r.pct));
    });

    const row = document.createElement('div');
    row.className = 'heatmap-row';

    const label = document.createElement('div');
    label.className = 'heatmap-label';
    label.textContent = name;
    row.appendChild(label);

    const cellsWrap = document.createElement('div');
    cellsWrap.className = 'heatmap-cells';

    const hours = Object.keys(hourly).sort();
    hours.forEach(h => {
      const vals = hourly[h];
      const avg = vals.reduce((a,b) => a+b, 0) / vals.length;
      const cell = document.createElement('div');
      cell.className = 'heatmap-cell';
      cell.style.backgroundColor = heatColor(avg);
      cell.addEventListener('mouseenter', (e) => {
        tooltip.style.display = 'block';
        tooltip.textContent = `${h}:00  ${avg.toFixed(1)}%  (${vals.length} checks)`;
        tooltip.style.left = e.clientX + 12 + 'px';
        tooltip.style.top = e.clientY - 36 + 'px';
      });
      cell.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
      cellsWrap.appendChild(cell);
    });

    row.appendChild(cellsWrap);
    container.appendChild(row);
  });

  const legend = document.createElement('div');
  legend.className = 'heatmap-legend';
  legend.innerHTML = '<span>0%</span>';
  [0, 25, 50, 75, 100].forEach(v => {
    legend.innerHTML += `<div class="swatch" style="background:${heatColor(v)}"></div>`;
  });
  legend.innerHTML += '<span>100%</span>';
  container.appendChild(legend);
}

function heatColor(pct) {
  if (pct >= 99.5) return 'rgba(34,197,94,0.7)';
  if (pct >= 95) return 'rgba(34,197,94,0.5)';
  if (pct >= 80) return 'rgba(34,197,94,0.3)';
  if (pct >= 50) return 'rgba(234,179,8,0.5)';
  if (pct >= 20) return 'rgba(234,179,8,0.3)';
  if (pct > 0) return 'rgba(239,68,68,0.5)';
  return 'rgba(239,68,68,0.25)';
}

function renderLog() {
  const logBody = document.getElementById('logBody');
  const recent = allData.slice(-100).reverse();
  logBody.innerHTML = recent.map(r => {
    const p = parseFloat(r.pct);
    const st = statusOf(p);
    const label = st.charAt(0).toUpperCase() + st.slice(1);
    const lat = r.avg_latency_ms ? parseFloat(r.avg_latency_ms).toFixed(1) + 'ms' : '--';
    const hostStr = r.port ? r.host+':'+r.port : r.host;
    const typeStr = r.type || 'tcp';
    const httpStatus = r.http_status ? r.http_status : '--';
    return `<tr><td>${r.timestamp}</td><td>${r.name}</td><td style="font-family:var(--mono);font-size:0.92em;color:var(--dim)">${hostStr}</td><td>${typeStr}</td>` +
      `<td>${r.successes}/${r.checks}</td><td>${r.pct}%</td><td>${lat}</td><td>${httpStatus}</td>` +
      `<td><span class="badge badge-${st}">${label}</span></td></tr>`;
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

    # CLI override: python3 dashboard.py [host] [port]
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
