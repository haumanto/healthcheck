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
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
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
    --text-dim: #3f3f46;
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

  .font-mono { font-family: var(--font-mono); }

  /* datetime-local picker icon */
  input[type="datetime-local"]::-webkit-calendar-picker-indicator {
    filter: invert(0.5);
    cursor: pointer;
    opacity: 0.5;
    transition: opacity 0.15s;
  }
  input[type="datetime-local"]::-webkit-calendar-picker-indicator:hover { opacity: 0.9; }

  /* custom scrollbar */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.14); }

  /* Tailwind-compatible utility classes for colors */
  .bg-bg { background-color: var(--bg); }
  .bg-surface { background-color: var(--surface); }
  .bg-surface-hover { background-color: var(--surface-hover); }
  .border-border { border-color: var(--border); }
  .text-text { color: var(--text); }
  .text-text-secondary { color: var(--text-secondary); }
  .text-text-tertiary { color: var(--text-tertiary); }
  .text-green { color: var(--green); }
  .text-yellow { color: var(--yellow); }
  .text-red { color: var(--red); }
  .bg-green { background-color: var(--green); }
  .bg-green-soft { background-color: var(--green-soft); }
  .bg-yellow-soft { background-color: var(--yellow-soft); }
  .bg-red-soft { background-color: var(--red-soft); }

  .hover\:bg-white\/[0\.02]:hover { background-color: rgba(255,255,255,0.02); }
  .hover\:bg-surface-hover:hover { background-color: var(--surface-hover); }
  .group:hover .group-hover\:bg-white\/[0\.02] { background-color: rgba(255,255,255,0.02); }
  .focus\:border-border-hover:focus { border-color: var(--border-hover); }
  .bg-white\/[0\.06] { background-color: rgba(255,255,255,0.06); }
  .bg-white\/[0\.02] { background-color: rgba(255,255,255,0.02); }
  .border-white\/[0\.04] { border-color: rgba(255,255,255,0.04); }
  .border-white\/[0\.08] { border-color: rgba(255,255,255,0.08); }
</style>
</head>
<body class="min-h-screen antialiased bg-bg">

<div class="mx-auto max-w-7xl px-6 py-16 sm:px-8 lg:px-12">

  <!-- Header -->
  <header class="mb-16">
    <div class="flex items-baseline justify-between">
      <div>
        <h1 class="text-[15px] font-semibold tracking-tight text-text">Health Check</h1>
        <p class="mt-1 text-xs text-text-tertiary" id="lastUpdate">Loading...</p>
      </div>
      <div class="flex items-center gap-2">
        <span class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-green opacity-40"></span>
          <span class="relative inline-flex h-2 w-2 rounded-full bg-green"></span>
        </span>
        <span class="text-[11px] font-medium tracking-wide text-text-tertiary uppercase">Live</span>
      </div>
    </div>
  </header>

  <!-- KPIs -->
  <div class="mb-14 flex gap-16 border-b border-border pb-10" id="summary"></div>

  <!-- Toolbar -->
  <div class="mb-10 flex flex-wrap items-center gap-3">
    <div class="inline-flex overflow-hidden rounded-lg border border-border">
      <button onclick="setRange(0.0417)" id="btn-1h" class="border-r border-border px-3.5 py-1.5 text-[11px] font-medium text-text-tertiary transition-colors hover:text-text-secondary hover:bg-white/[0.02]">1h</button>
      <button onclick="setRange(0.25)" id="btn-6h" class="border-r border-border px-3.5 py-1.5 text-[11px] font-medium text-text-tertiary transition-colors hover:text-text-secondary hover:bg-white/[0.02]">6h</button>
      <button onclick="setRange(1)" id="btn-1d" class="active bg-white/[0.06] px-3.5 py-1.5 text-[11px] font-medium text-text transition-colors">24h</button>
      <button onclick="setRange(3)" id="btn-3d" class="border-l border-border px-3.5 py-1.5 text-[11px] font-medium text-text-tertiary transition-colors hover:text-text-secondary hover:bg-white/[0.02]">3d</button>
      <button onclick="setRange(7)" id="btn-7d" class="border-l border-border px-3.5 py-1.5 text-[11px] font-medium text-text-tertiary transition-colors hover:text-text-secondary hover:bg-white/[0.02]">7d</button>
    </div>

    <div class="h-4 w-px bg-border"></div>

    <label class="text-[10px] font-medium tracking-wider text-text-tertiary uppercase">From</label>
    <input type="datetime-local" id="filterFrom" onchange="applyCustomFilter()" class="rounded-md border border-border bg-transparent px-2.5 py-1 text-[11px] text-text-secondary outline-none transition-colors focus:border-border-hover">

    <label class="text-[10px] font-medium tracking-wider text-text-tertiary uppercase">To</label>
    <input type="datetime-local" id="filterTo" onchange="applyCustomFilter()" class="rounded-md border border-border bg-transparent px-2.5 py-1 text-[11px] text-text-secondary outline-none transition-colors focus:border-border-hover">

    <button onclick="clearCustomFilter()" class="rounded-md px-2.5 py-1 text-[11px] font-medium text-text-tertiary transition-colors hover:text-text-secondary">Reset</button>

    <div class="h-4 w-px bg-border"></div>

    <select id="filterTarget" onchange="applyTargetFilter()" class="rounded-md border border-border bg-transparent px-2.5 py-1 text-[11px] text-text-secondary outline-none transition-colors focus:border-border-hover">
      <option value="">All targets</option>
    </select>

    <select id="filterType" onchange="applyTargetFilter()" class="rounded-md border border-border bg-transparent px-2.5 py-1 text-[11px] text-text-secondary outline-none transition-colors focus:border-border-hover">
      <option value="">All types</option>
      <option value="tcp">TCP</option>
      <option value="ping">Ping</option>
      <option value="http">HTTP</option>
    </select>

    <span class="ml-auto text-[10px] tracking-wide text-text-tertiary">Auto-refresh 60s</span>
  </div>

  <!-- Cards -->
  <div class="mb-14 grid grid-cols-1 gap-px overflow-hidden rounded-xl bg-border sm:grid-cols-2 lg:grid-cols-3" id="cards"></div>

  <!-- Uptime Chart -->
  <div class="mb-5 rounded-xl border border-border bg-surface p-7">
    <div class="mb-5 text-[10px] font-medium tracking-[0.08em] text-text-tertiary uppercase">Uptime</div>
    <div class="relative h-44">
      <canvas id="uptimeChart"></canvas>
    </div>
  </div>

  <!-- Latency Chart -->
  <div class="mb-5 rounded-xl border border-border bg-surface p-7">
    <div class="mb-5 text-[10px] font-medium tracking-[0.08em] text-text-tertiary uppercase">Response Time</div>
    <div class="relative h-44">
      <canvas id="latencyChart"></canvas>
    </div>
  </div>

  <!-- Heatmap -->
  <div class="mb-5 rounded-xl border border-border bg-surface p-7">
    <div class="mb-5 text-[10px] font-medium tracking-[0.08em] text-text-tertiary uppercase">Availability</div>
    <div id="heatmap"></div>
  </div>

  <!-- Log Table -->
  <div class="overflow-hidden rounded-xl border border-border bg-surface">
    <div class="px-7 pt-5">
      <div class="text-[10px] font-medium tracking-[0.08em] text-text-tertiary uppercase">Event Log</div>
    </div>
    <div class="max-h-80 overflow-y-auto px-7 pb-5">
      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">Time</th>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">Target</th>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">Host</th>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">Type</th>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">Result</th>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">Uptime</th>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">Latency</th>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">HTTP</th>
            <th class="sticky top-0 bg-surface py-2.5 text-left text-[10px] font-medium tracking-wider text-text-tertiary uppercase">State</th>
          </tr>
        </thead>
        <tbody id="logBody"></tbody>
      </table>
    </div>
  </div>

</div>

<!-- Tooltip -->
<div id="tooltip" class="pointer-events-none fixed z-50 hidden whitespace-nowrap rounded-lg border border-white/[0.08] bg-[#131316] px-3 py-2 text-[11px] text-text shadow-2xl"></div>

<script>
const LINE_COLORS = ['#71717a','#a1a1aa','#d4d4d8','#52525b','#a3a3a3','#737373','#52525b'];
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
  document.querySelectorAll('.overflow-hidden button').forEach(b => {
    b.classList.remove('active', 'bg-white/[0.06]', 'text-text');
    b.classList.add('text-text-tertiary');
  });
  const labels = {0.0417:'1h', 0.25:'6h', 1:'1d', 3:'3d', 7:'7d'};
  const btn = document.getElementById('btn-' + labels[days]);
  if (btn) { btn.classList.add('active', 'bg-white/[0.06]', 'text-text'); btn.classList.remove('text-text-tertiary'); }
  fetchData();
}

function applyCustomFilter() {
  const from = document.getElementById('filterFrom').value;
  const to = document.getElementById('filterTo').value;
  if (!from && !to) return;
  customFilterActive = true;
  document.querySelectorAll('.overflow-hidden button').forEach(b => {
    b.classList.remove('active', 'bg-white/[0.06]', 'text-text');
    b.classList.add('text-text-tertiary');
  });
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
function statusBg(st) { return st==='ok'?'bg-green-soft text-green':st==='degraded'?'bg-yellow-soft text-yellow':'bg-red-soft text-red'; }

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
    <div class="flex flex-col gap-0.5">
      <div class="text-[10px] font-medium tracking-[0.08em] text-text-tertiary uppercase">Targets</div>
      <div class="font-mono text-[28px] font-semibold leading-none tracking-tight text-text">${total}</div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-[10px] font-medium tracking-[0.08em] text-text-tertiary uppercase">Uptime</div>
      <div class="font-mono text-[28px] font-semibold leading-none tracking-tight" style="color:${statusColor(parseFloat(pct))}">${pct}<span class="ml-0.5 text-sm font-normal text-text-tertiary">%</span></div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-[10px] font-medium tracking-[0.08em] text-text-tertiary uppercase">Latency</div>
      <div class="font-mono text-[28px] font-semibold leading-none tracking-tight text-text">${avgLat}<span class="ml-0.5 text-sm font-normal text-text-tertiary">ms</span></div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-[10px] font-medium tracking-[0.08em] text-text-tertiary uppercase">Checks</div>
      <div class="font-mono text-[28px] font-semibold leading-none tracking-tight text-text">${checks}</div>
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
    c.className = 'bg-surface p-6 transition-colors duration-150 hover:bg-surface-hover';
    c.innerHTML = `
      <div class="mb-5 flex items-start justify-between">
        <div class="min-w-0">
          <div class="truncate text-[13px] font-medium text-text">${name}</div>
          <div class="mt-0.5 truncate font-mono text-[10px] text-text-tertiary">${latest.port?latest.host+':'+latest.port:latest.host} / ${latest.type||'tcp'}</div>
        </div>
        <span class="inline-flex shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${statusBg(st)}">${st}</span>
      </div>
      <div class="mb-1 flex items-end gap-6">
        <div class="font-mono text-[32px] font-semibold leading-none tracking-tight" style="color:${statusColor(cur)}">${cur}<span class="ml-0.5 text-sm font-normal text-text-tertiary">%</span></div>
        <div class="flex flex-col gap-0.5 pb-1">
          <div class="flex items-center gap-3 text-[11px] text-text-tertiary">
            <span>avg</span>
            <span class="font-mono text-text-secondary">${avg}%</span>
          </div>
          <div class="flex items-center gap-3 text-[11px] text-text-tertiary">
            <span>latency</span>
            <span class="font-mono text-text-secondary">${aLat}ms</span>
          </div>
        </div>
      </div>
      <div class="h-12"><canvas id="${cid}"></canvas></div>
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
      plugins: { ...chartDefaults.plugins, legend:{display:true,position:'top',align:'end',labels:{color:'#52525b',boxWidth:6,boxHeight:6,padding:14,font:{size:10,family:"'Inter', sans-serif"},usePointStyle:true,pointStyle:'circle'}}, tooltip:{...chartDefaults.plugins.tooltip,mode:'index',intersect:false,callbacks:{label:c=>` ${c.dataset.label}  ${c.parsed.y}%`}} },
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
      plugins: { ...chartDefaults.plugins, legend:{display:true,position:'top',align:'end',labels:{color:'#52525b',boxWidth:6,boxHeight:6,padding:14,font:{size:10,family:"'Inter', sans-serif"},usePointStyle:true,pointStyle:'circle'}}, tooltip:{...chartDefaults.plugins.tooltip,mode:'index',intersect:false,callbacks:{label:c=>` ${c.dataset.label}  ${c.parsed.y.toFixed(1)}ms`}} },
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
    const row = document.createElement('div'); row.className='flex items-center mb-2';
    const lbl = document.createElement('div'); lbl.className='w-32 shrink-0 truncate text-[11px] text-text-tertiary'; lbl.textContent=name; row.appendChild(lbl);
    const wrap = document.createElement('div'); wrap.className='flex flex-wrap gap-1';
    Object.keys(hourly).sort().forEach(h => {
      const vs=hourly[h]; const avg=vs.reduce((a,b)=>a+b,0)/vs.length;
      const c=document.createElement('div'); c.className='h-3.5 w-3.5 rounded-[3px] cursor-pointer transition-transform duration-100 hover:scale-[1.4]'; c.style.backgroundColor=heatColor(avg);
      c.addEventListener('mouseenter',e=>{tip.style.display='block';tip.textContent=`${h}:00  ${avg.toFixed(1)}%  (${vs.length})`;tip.style.left=e.clientX+12+'px';tip.style.top=e.clientY-36+'px';});
      c.addEventListener('mouseleave',()=>{tip.style.display='none';});
      wrap.appendChild(c);
    });
    row.appendChild(wrap); box.appendChild(row);
  });
  const leg=document.createElement('div'); leg.className='mt-3.5 flex items-center gap-1 pl-32 text-[10px] text-text-tertiary';
  leg.innerHTML='<span>0%</span>';
  [0,25,50,75,100].forEach(v=>{leg.innerHTML+=`<div class="h-3 w-3 rounded-[3px]" style="background:${heatColor(v)}"></div>`;});
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
    return `<tr class="group transition-colors hover:bg-white/[0.02]">
      <td class="py-2.5 border-b border-border font-mono text-[11px] text-text-secondary">${r.timestamp}</td>
      <td class="py-2.5 border-b border-border text-[11px] text-text">${r.name}</td>
      <td class="py-2.5 border-b border-border font-mono text-[11px] text-text-tertiary">${host}</td>
      <td class="py-2.5 border-b border-border text-[11px] text-text-secondary">${r.type||'tcp'}</td>
      <td class="py-2.5 border-b border-border font-mono text-[11px] text-text-secondary">${r.successes}/${r.checks}</td>
      <td class="py-2.5 border-b border-border font-mono text-[11px] text-text-secondary">${r.pct}%</td>
      <td class="py-2.5 border-b border-border font-mono text-[11px] text-text-secondary">${lat}</td>
      <td class="py-2.5 border-b border-border font-mono text-[11px] text-text-secondary">${http}</td>
      <td class="py-2.5 border-b border-border"><span class="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${statusBg(st)}">${st}</span></td>
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
