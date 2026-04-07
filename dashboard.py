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
    --bg: #0f1117; --card: #1a1d27; --border: #2a2d3a; --text: #e1e4ed;
    --dim: #8b8fa3; --green: #22c55e; --yellow: #eab308; --red: #ef4444;
    --blue: #3b82f6; --purple: #a855f7; --cyan: #06b6d4; --orange: #f97316;
    --pink: #ec4899;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 20px; }
  h1 { font-size: 1.4em; margin-bottom: 4px; }
  h2 { font-size: 1.05em; margin-bottom: 12px; }
  .subtitle { color: var(--dim); font-size: 0.85em; margin-bottom: 16px; }

  /* Summary bar */
  .summary { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
  .summary-item { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px 20px; flex: 1; min-width: 140px; }
  .summary-label { font-size: 0.75em; color: var(--dim); text-transform: uppercase; letter-spacing: 0.5px; }
  .summary-value { font-size: 1.6em; font-weight: 700; margin-top: 2px; }

  /* Controls */
  .controls { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
  .controls button { background: var(--card); color: var(--text); border: 1px solid var(--border); padding: 6px 14px; border-radius: 6px; font-size: 0.82em; cursor: pointer; transition: all 0.15s; }
  .controls button.active { background: var(--blue); border-color: var(--blue); }
  .controls button:hover { border-color: var(--blue); }
  .refresh-info { color: var(--dim); font-size: 0.78em; margin-left: 8px; }
  .controls input[type="datetime-local"] { background: var(--card); color: var(--text); border: 1px solid var(--border); padding: 5px 10px; border-radius: 6px; font-size: 0.82em; }
  .controls input[type="datetime-local"]::-webkit-calendar-picker-indicator { filter: invert(0.7); }
  .controls select { background: var(--card); color: var(--text); border: 1px solid var(--border); padding: 6px 10px; border-radius: 6px; font-size: 0.82em; cursor: pointer; }
  .controls .sep { color: var(--dim); font-size: 0.8em; }
  .filter-row { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }

  /* Target cards grid */
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .card-title { font-size: 1em; font-weight: 600; }
  .card-host { font-size: 0.78em; color: var(--dim); }
  .badge { padding: 2px 8px; border-radius: 10px; font-size: 0.72em; font-weight: 600; }
  .badge-ok { background: rgba(34,197,94,0.15); color: var(--green); }
  .badge-degraded { background: rgba(234,179,8,0.15); color: var(--yellow); }
  .badge-down { background: rgba(239,68,68,0.15); color: var(--red); }

  .card-metrics { display: flex; align-items: center; gap: 20px; margin-bottom: 10px; }
  .gauge-wrap { position: relative; width: 80px; height: 80px; flex-shrink: 0; }
  .gauge-wrap canvas { width: 80px; height: 80px; }
  .gauge-label { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 1.1em; font-weight: 700; }
  .metric-stats { display: flex; flex-direction: column; gap: 4px; font-size: 0.8em; color: var(--dim); }
  .metric-stats span { display: flex; justify-content: space-between; gap: 12px; }
  .metric-stats .val { color: var(--text); font-weight: 500; }

  .chart-container { position: relative; height: 160px; }

  /* Full-width chart sections */
  .section { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 20px; }
  .section .chart-wide { position: relative; height: 240px; }

  /* Heatmap */
  .heatmap { margin-bottom: 20px; }
  .heatmap-row { display: flex; align-items: center; margin-bottom: 4px; }
  .heatmap-label { width: 140px; font-size: 0.78em; color: var(--dim); flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .heatmap-cells { display: flex; gap: 2px; flex-wrap: wrap; flex: 1; }
  .heatmap-cell { width: 14px; height: 14px; border-radius: 2px; cursor: pointer; position: relative; }
  .heatmap-cell:hover { outline: 1px solid var(--text); }
  .heatmap-legend { display: flex; align-items: center; gap: 6px; margin-top: 8px; padding-left: 140px; font-size: 0.72em; color: var(--dim); }
  .heatmap-legend .swatch { width: 12px; height: 12px; border-radius: 2px; }
  .tooltip { display: none; position: fixed; background: #252830; border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; font-size: 0.75em; color: var(--text); z-index: 1000; pointer-events: none; white-space: nowrap; }

  /* Log table */
  .table-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 0.8em; }
  th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  th { color: var(--dim); font-weight: 500; position: sticky; top: 0; background: var(--card); }
  .scroll-table { max-height: 350px; overflow-y: auto; }

  @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } .summary { flex-direction: column; } }
</style>
</head>
<body>

<h1>Health Check Dashboard</h1>
<div class="subtitle" id="lastUpdate">Loading...</div>

<!-- Summary -->
<div class="summary" id="summary"></div>

<!-- Time range -->
<div class="controls">
  <button onclick="setRange(0.0417)" id="btn-1h">1H</button>
  <button onclick="setRange(0.25)" id="btn-6h">6H</button>
  <button onclick="setRange(1)" id="btn-1d" class="active">1D</button>
  <button onclick="setRange(3)" id="btn-3d">3D</button>
  <button onclick="setRange(7)" id="btn-7d">7D</button>
  <span class="refresh-info">Auto-refresh: 60s</span>
</div>
<div class="filter-row">
  <span class="sep">From</span>
  <input type="datetime-local" id="filterFrom" onchange="applyCustomFilter()">
  <span class="sep">To</span>
  <input type="datetime-local" id="filterTo" onchange="applyCustomFilter()">
  <button class="controls" onclick="clearCustomFilter()" style="background:var(--card);color:var(--text);border:1px solid var(--border);padding:6px 14px;border-radius:6px;font-size:0.82em;cursor:pointer;">Clear</button>
  <span class="sep">|</span>
  <span class="sep">Target</span>
  <select id="filterTarget" onchange="applyTargetFilter()">
    <option value="">All Targets</option>
  </select>
  <span class="sep">Type</span>
  <select id="filterType" onchange="applyTargetFilter()">
    <option value="">All Types</option>
    <option value="tcp">TCP</option>
    <option value="ping">Ping</option>
  </select>
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
  <h2>Latency (ms)</h2>
  <div class="chart-wide"><canvas id="latencyChart"></canvas></div>
</div>

<!-- Heatmap -->
<div class="section">
  <h2>Uptime Heatmap (per hour)</h2>
  <div id="heatmap" class="heatmap"></div>
</div>

<!-- Log table -->
<div class="table-card">
  <h2>Recent Checks</h2>
  <div class="scroll-table">
    <table>
      <thead><tr><th>Time</th><th>Target</th><th>Host</th><th>Type</th><th>Success</th><th>%</th><th>Latency</th><th>Status</th></tr></thead>
      <tbody id="logBody"></tbody>
    </table>
  </div>
</div>

<div class="tooltip" id="tooltip"></div>

<script>
const COLORS = ['#22c55e','#3b82f6','#a855f7','#f97316','#ec4899','#06b6d4','#eab308','#ef4444','#14b8a6','#f43f5e'];
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
  animation: { duration: 400 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#252830',
      borderColor: '#2a2d3a',
      borderWidth: 1,
      titleColor: '#e1e4ed',
      bodyColor: '#8b8fa3',
      padding: 8,
      cornerRadius: 6,
      displayColors: true,
    }
  },
  scales: {
    x: {
      ticks: { color: '#8b8fa3', maxRotation: 0, autoSkip: true, maxTicksLimit: 12, font: { size: 10 } },
      grid: { color: 'rgba(42,45,58,0.5)', drawBorder: false },
    },
    y: {
      ticks: { color: '#8b8fa3', font: { size: 10 } },
      grid: { color: 'rgba(42,45,58,0.5)', drawBorder: false },
    }
  }
};

function setRange(days) {
  currentRange = days;
  customFilterActive = false;
  document.getElementById('filterFrom').value = '';
  document.getElementById('filterTo').value = '';
  document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
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
  // Deactivate preset buttons
  document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
  // Fetch enough data to cover the range, then filter client-side
  const days = 7; // fetch max range, filter locally
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

  // Custom time filter
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

  // Target filter
  const targetFilter = document.getElementById('filterTarget').value;
  if (targetFilter) {
    data = data.filter(d => d.name === targetFilter);
  }

  // Type filter
  const typeFilter = document.getElementById('filterType').value;
  if (typeFilter) {
    data = data.filter(d => (d.type || 'tcp') === typeFilter);
  }

  allData = data;
}

async function fetchData() {
  try {
    const r = await fetch('/api/data?days=' + currentRange);
    rawData = await r.json();
    // Populate target dropdown
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
  canvas.width = 80 * dpr;
  canvas.height = 80 * dpr;
  ctx.scale(dpr, dpr);
  const cx = 40, cy = 40, r = 32, lw = 7;
  const startAngle = 0.75 * Math.PI;
  const totalAngle = 1.5 * Math.PI;

  // Background arc
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, startAngle + totalAngle);
  ctx.strokeStyle = '#2a2d3a';
  ctx.lineWidth = lw;
  ctx.lineCap = 'round';
  ctx.stroke();

  // Value arc
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
    <div class="summary-item"><div class="summary-label">Avg Latency</div><div class="summary-value" style="color:var(--blue)">${avgLat}ms</div></div>
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
        <div><div class="card-title">${name}</div><div class="card-host">${latest.port ? latest.host+':'+latest.port : latest.host} [${latest.type || 'tcp'}]</div></div>
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

    // Draw gauge
    drawGauge(document.getElementById('gauge-' + idx), curPct);

    // Card chart: uptime line
    const labels = rows.map(r => r.timestamp.split(' ')[1] || r.timestamp);
    const values = rows.map(r => parseFloat(r.pct));
    const color = COLORS[idx % COLORS.length];

    const ctx = document.getElementById(cardId).getContext('2d');
    cardCharts[cardId] = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: color,
          backgroundColor: color + '20',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHitRadius: 8,
          borderWidth: 2,
        }]
      },
      options: {
        ...chartDefaults,
        scales: {
          ...chartDefaults.scales,
          y: { ...chartDefaults.scales.y, min: 0, max: 100, ticks: { ...chartDefaults.scales.y.ticks, callback: v => v + '%' } }
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

  // Combined uptime chart
  renderUptimeChart(byTarget, targetNames);
  // Latency chart
  renderLatencyChart(byTarget, targetNames);
  // Heatmap
  renderHeatmap(byTarget, targetNames);
  // Log table
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
      backgroundColor: COLORS[i % COLORS.length] + '15',
      fill: false,
      tension: 0.3,
      pointRadius: 0,
      pointHitRadius: 8,
      borderWidth: 2,
    };
  });

  // Use the longest target's timestamps as labels
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
        legend: { display: true, labels: { color: '#8b8fa3', boxWidth: 12, padding: 16, font: { size: 11 } } },
        tooltip: { ...chartDefaults.plugins.tooltip, mode: 'index', intersect: false, callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}%` } }
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
      tension: 0.3,
      pointRadius: 0,
      pointHitRadius: 8,
      borderWidth: 2,
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
        legend: { display: true, labels: { color: '#8b8fa3', boxWidth: 12, padding: 16, font: { size: 11 } } },
        tooltip: { ...chartDefaults.plugins.tooltip, mode: 'index', intersect: false, callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}ms` } }
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
    // Group by hour
    const hourly = {};
    rows.forEach(r => {
      const h = r.timestamp.substring(0, 13); // "YYYY-MM-DD HH"
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

    // Sort hours chronologically
    const hours = Object.keys(hourly).sort();
    hours.forEach(h => {
      const vals = hourly[h];
      const avg = vals.reduce((a,b) => a+b, 0) / vals.length;
      const cell = document.createElement('div');
      cell.className = 'heatmap-cell';
      cell.style.backgroundColor = heatColor(avg);
      cell.addEventListener('mouseenter', (e) => {
        tooltip.style.display = 'block';
        tooltip.textContent = `${h}:00 — ${avg.toFixed(1)}% (${vals.length} checks)`;
        tooltip.style.left = e.clientX + 10 + 'px';
        tooltip.style.top = e.clientY - 30 + 'px';
      });
      cell.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
      cellsWrap.appendChild(cell);
    });

    row.appendChild(cellsWrap);
    container.appendChild(row);
  });

  // Legend
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
  if (pct >= 99.5) return '#166534';
  if (pct >= 95) return '#22c55e';
  if (pct >= 80) return '#86efac';
  if (pct >= 50) return '#eab308';
  if (pct >= 20) return '#f97316';
  if (pct > 0) return '#ef4444';
  return '#7f1d1d';
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
    return `<tr><td>${r.timestamp}</td><td>${r.name}</td><td>${hostStr}</td><td>${typeStr}</td>` +
      `<td>${r.successes}/${r.checks}</td><td>${r.pct}%</td><td>${lat}</td>` +
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
