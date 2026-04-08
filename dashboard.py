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
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0a0a0b;
    --surface: #111113;
    --surface-hover: #161618;
    --border: rgba(255,255,255,0.05);
    --text: #e4e4e7;
    --text-2: #a1a1aa;
    --text-3: #52525b;
    --green: #34d399;
    --yellow: #fbbf24;
    --red: #f87171;
    --mono: ui-monospace, 'SF Mono', 'Cascadia Mono', monospace;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
    line-height: 1.5;
  }

  .page { max-width: 1200px; margin: 0 auto; padding: 48px 32px 64px; }

  /* --- Header --- */
  .header { margin-bottom: 48px; }
  .header h1 {
    font-size: 1.25em;
    font-weight: 500;
    letter-spacing: -0.01em;
    color: var(--text);
  }
  .header .meta {
    font-size: 0.75em;
    color: var(--text-3);
    margin-top: 4px;
  }

  /* --- Summary --- */
  .kpis {
    display: flex;
    gap: 48px;
    padding-bottom: 40px;
    margin-bottom: 40px;
    border-bottom: 1px solid var(--border);
  }
  .kpi {}
  .kpi-label { font-size: 0.7em; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500; }
  .kpi-value { font-size: 2.2em; font-weight: 600; letter-spacing: -0.03em; margin-top: 2px; color: var(--text); }
  .kpi-value .unit { font-size: 0.35em; font-weight: 400; color: var(--text-3); margin-left: 1px; }

  /* --- Toolbar --- */
  .bar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 36px;
  }
  .seg { display: inline-flex; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
  .seg button {
    background: transparent;
    color: var(--text-3);
    border: none;
    padding: 6px 13px;
    font-size: 0.72em;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s;
    letter-spacing: 0.01em;
    border-right: 1px solid var(--border);
  }
  .seg button:last-child { border-right: none; }
  .seg button:hover { color: var(--text-2); background: rgba(255,255,255,0.03); }
  .seg button.active { color: var(--text); background: rgba(255,255,255,0.07); }

  .bar .spacer { width: 1px; height: 20px; background: var(--border); margin: 0 2px; }
  .bar label { font-size: 0.68em; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.04em; font-weight: 500; }
  .bar input[type="datetime-local"],
  .bar select {
    background: transparent;
    color: var(--text-2);
    border: 1px solid var(--border);
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 0.72em;
    font-family: inherit;
    outline: none;
    transition: border-color 0.12s;
  }
  .bar input:focus, .bar select:focus { border-color: rgba(255,255,255,0.15); }
  .bar input[type="datetime-local"]::-webkit-calendar-picker-indicator { filter: invert(0.4); cursor: pointer; }
  .bar .ghost {
    background: transparent;
    color: var(--text-3);
    border: none;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 0.72em;
    cursor: pointer;
    transition: color 0.12s;
  }
  .bar .ghost:hover { color: var(--text-2); }
  .bar .end { margin-left: auto; font-size: 0.68em; color: var(--text-3); }

  /* --- Cards --- */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1px;
    background: var(--border);
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 48px;
  }
  .card {
    background: var(--surface);
    padding: 24px 28px;
    transition: background 0.15s;
  }
  .card:hover { background: var(--surface-hover); }
  .card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
  .card-name { font-size: 0.82em; font-weight: 500; color: var(--text); }
  .card-sub { font-size: 0.68em; color: var(--text-3); margin-top: 2px; font-family: var(--mono); }
  .pill {
    font-size: 0.62em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    padding: 2px 8px;
    border-radius: 100px;
  }
  .pill-ok { color: var(--green); background: rgba(52,211,153,0.1); }
  .pill-degraded { color: var(--yellow); background: rgba(251,191,36,0.1); }
  .pill-down { color: var(--red); background: rgba(248,113,113,0.1); }

  .card-body { display: flex; align-items: flex-end; gap: 24px; }
  .card-pct { font-size: 2.4em; font-weight: 600; letter-spacing: -0.04em; font-family: var(--mono); line-height: 1; }
  .card-detail { flex: 1; display: flex; flex-direction: column; gap: 3px; font-size: 0.72em; color: var(--text-3); padding-bottom: 4px; }
  .card-detail span { display: flex; justify-content: space-between; }
  .card-detail .v { color: var(--text-2); font-family: var(--mono); }

  .card-spark { height: 48px; margin-top: 16px; }

  /* --- Sections --- */
  .panel {
    background: var(--surface);
    border-radius: 12px;
    padding: 28px;
    margin-bottom: 24px;
  }
  .panel-label {
    font-size: 0.68em;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
    margin-bottom: 20px;
  }
  .chart-area { position: relative; height: 180px; }

  /* --- Heatmap --- */
  .hm-row { display: flex; align-items: center; margin-bottom: 8px; }
  .hm-name { width: 120px; font-size: 0.7em; color: var(--text-3); flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hm-cells { display: flex; gap: 3px; flex-wrap: wrap; }
  .hm-cell { width: 14px; height: 14px; border-radius: 3px; cursor: pointer; transition: transform 0.1s, opacity 0.1s; }
  .hm-cell:hover { transform: scale(1.4); }
  .hm-legend { display: flex; align-items: center; gap: 4px; margin-top: 14px; padding-left: 120px; font-size: 0.64em; color: var(--text-3); }
  .hm-legend .sw { width: 12px; height: 12px; border-radius: 3px; }
  .tip {
    display: none;
    position: fixed;
    background: #1a1a1e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.72em;
    color: var(--text);
    z-index: 1000;
    pointer-events: none;
    white-space: nowrap;
    box-shadow: 0 12px 32px rgba(0,0,0,0.6);
  }

  /* --- Table --- */
  .tbl-wrap {
    background: var(--surface);
    border-radius: 12px;
    overflow: hidden;
  }
  .tbl-header { padding: 20px 28px 0; }
  .tbl-scroll { max-height: 360px; overflow-y: auto; padding: 0 28px 20px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 0.74em; }
  th { color: var(--text-3); font-weight: 500; font-size: 0.66em; text-transform: uppercase; letter-spacing: 0.05em; position: sticky; top: 0; background: var(--surface); }
  td { color: var(--text-2); }
  .mono { font-family: var(--mono); font-size: 0.95em; }
  tr:last-child td { border-bottom: none; }

  @media (max-width: 768px) {
    .page { padding: 24px 16px 40px; }
    .kpis { gap: 24px; flex-wrap: wrap; }
    .grid { grid-template-columns: 1fr; }
    .bar { gap: 6px; }
  }
</style>
</head>
<body>

<div class="page">

<div class="header">
  <h1>Health Check</h1>
  <div class="meta" id="lastUpdate">Loading...</div>
</div>

<div class="kpis" id="summary"></div>

<div class="bar">
  <div class="seg">
    <button onclick="setRange(0.0417)" id="btn-1h">1h</button>
    <button onclick="setRange(0.25)" id="btn-6h">6h</button>
    <button class="active" onclick="setRange(1)" id="btn-1d">24h</button>
    <button onclick="setRange(3)" id="btn-3d">3d</button>
    <button onclick="setRange(7)" id="btn-7d">7d</button>
  </div>
  <div class="spacer"></div>
  <label>From</label>
  <input type="datetime-local" id="filterFrom" onchange="applyCustomFilter()">
  <label>To</label>
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

<div class="grid" id="cards"></div>

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
const LINE_COLORS = ['#52525b','#71717a','#a1a1aa','#d4d4d8','#3f3f46','#a3a3a3','#737373'];
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
      backgroundColor: '#1a1a1e',
      borderColor: 'rgba(255,255,255,0.08)',
      borderWidth: 1,
      titleColor: '#e4e4e7',
      bodyColor: '#a1a1aa',
      padding: 10,
      cornerRadius: 8,
      displayColors: false,
      titleFont: { weight: '500' },
    }
  },
  scales: {
    x: {
      ticks: { color: '#3f3f46', maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 10 } },
      grid: { color: 'rgba(255,255,255,0.025)', drawBorder: false },
      border: { display: false },
    },
    y: {
      ticks: { color: '#3f3f46', font: { size: 10 } },
      grid: { color: 'rgba(255,255,255,0.025)', drawBorder: false },
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
    <div class="kpi"><div class="kpi-label">Targets</div><div class="kpi-value">${total}</div></div>
    <div class="kpi"><div class="kpi-label">Uptime</div><div class="kpi-value" style="color:${statusColor(parseFloat(pct))}">${pct}<span class="unit">%</span></div></div>
    <div class="kpi"><div class="kpi-label">Latency</div><div class="kpi-value">${avgLat}<span class="unit">ms</span></div></div>
    <div class="kpi"><div class="kpi-label">Checks</div><div class="kpi-value">${checks}</div></div>
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
        <div><div class="card-name">${name}</div><div class="card-sub">${latest.port?latest.host+':'+latest.port:latest.host} / ${latest.type||'tcp'}</div></div>
        <span class="pill pill-${st}">${st}</span>
      </div>
      <div class="card-body">
        <div class="card-pct" style="color:${statusColor(cur)}">${cur}%</div>
        <div class="card-detail">
          <span>avg <span class="v">${avg}%</span></span>
          <span>latency <span class="v">${aLat}ms</span></span>
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
      plugins: { ...chartDefaults.plugins, legend:{display:true,position:'top',align:'end',labels:{color:'#52525b',boxWidth:6,boxHeight:6,padding:14,font:{size:10},usePointStyle:true,pointStyle:'circle'}}, tooltip:{...chartDefaults.plugins.tooltip,mode:'index',intersect:false,callbacks:{label:c=>` ${c.dataset.label}  ${c.parsed.y}%`}} },
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
      plugins: { ...chartDefaults.plugins, legend:{display:true,position:'top',align:'end',labels:{color:'#52525b',boxWidth:6,boxHeight:6,padding:14,font:{size:10},usePointStyle:true,pointStyle:'circle'}}, tooltip:{...chartDefaults.plugins.tooltip,mode:'index',intersect:false,callbacks:{label:c=>` ${c.dataset.label}  ${c.parsed.y.toFixed(1)}ms`}} },
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
  const leg=document.createElement('div'); leg.className='hm-legend'; leg.innerHTML='<span>0%</span>';
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
    return `<tr><td class="mono">${r.timestamp}</td><td>${r.name}</td><td class="mono" style="color:var(--text-3)">${host}</td><td>${r.type||'tcp'}</td><td class="mono">${r.successes}/${r.checks}</td><td class="mono">${r.pct}%</td><td class="mono">${lat}</td><td class="mono">${http}</td><td><span class="pill pill-${st}">${st}</span></td></tr>`;
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
