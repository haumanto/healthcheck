#!/usr/bin/env python3
"""
Health Check Monitor - checks connection percentage per minute to targets.
Runs checks_per_minute attempts within each minute, records success % and latency.
Results stored as CSV: timestamp, target_name, host, port, checks, successes, pct, avg_latency_ms
"""

import json
import os
import sys
import socket
import time
import csv
import glob
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"

CSV_FIELDS = ["timestamp", "name", "host", "port", "checks", "successes", "pct", "avg_latency_ms"]


def load_config():
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    cfg["data_dir"] = str(SCRIPT_DIR / cfg["data_dir"])
    return cfg


def check_tcp(host, port, timeout):
    """Attempt a TCP connection. Returns (success, latency_ms)."""
    try:
        start = time.monotonic()
        with socket.create_connection((host, port), timeout=timeout):
            latency = (time.monotonic() - start) * 1000
            return True, round(latency, 2)
    except (socket.timeout, socket.error, OSError):
        return False, 0.0


def check_target(target, count, timeout):
    """Run `count` checks against a target, spaced evenly within ~55 seconds."""
    interval = 55.0 / max(count, 1)
    successes = 0
    latencies = []
    for i in range(count):
        ok, lat = check_tcp(target["host"], target["port"], timeout)
        if ok:
            successes += 1
            latencies.append(lat)
        if i < count - 1:
            time.sleep(interval)
    avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    return successes, avg_lat


def run_checks(config):
    """Run one minute's worth of checks against all targets in parallel."""
    targets = config["targets"]
    count = config["checks_per_minute"]
    timeout = config["timeout_seconds"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    results = []
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        futures = {}
        for t in targets:
            f = pool.submit(check_target, t, count, timeout)
            futures[f] = t

        for f in as_completed(futures):
            t = futures[f]
            successes, avg_lat = f.result()
            pct = round(successes / count * 100, 1)
            results.append({
                "timestamp": ts,
                "name": t["name"],
                "host": t["host"],
                "port": t["port"],
                "checks": count,
                "successes": successes,
                "pct": pct,
                "avg_latency_ms": avg_lat,
            })

    return results


def save_results(results, data_dir):
    """Append results to daily CSV file."""
    os.makedirs(data_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(data_dir, f"{today}.csv")

    file_exists = os.path.exists(filepath)
    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)


def cleanup_old_data(data_dir, retention_days):
    """Remove CSV files older than retention_days."""
    cutoff = datetime.now() - timedelta(days=retention_days)
    for filepath in glob.glob(os.path.join(data_dir, "*.csv")):
        filename = os.path.basename(filepath)
        try:
            file_date = datetime.strptime(filename.replace(".csv", ""), "%Y-%m-%d")
            if file_date < cutoff:
                os.remove(filepath)
                print(f"Cleaned up old data: {filename}")
        except ValueError:
            pass


def main():
    config = load_config()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking {len(config['targets'])} target(s), "
          f"{config['checks_per_minute']} checks each...")

    results = run_checks(config)
    save_results(results, config["data_dir"])
    cleanup_old_data(config["data_dir"], config["retention_days"])

    for r in results:
        status = "OK" if r["pct"] == 100 else "DEGRADED" if r["pct"] > 0 else "DOWN"
        print(f"  {r['name']:20s} {r['host']:20s}:{r['port']:<5d}  "
              f"{r['successes']}/{r['checks']}  {r['pct']:5.1f}%  "
              f"{r['avg_latency_ms']:6.1f}ms  [{status}]")


if __name__ == "__main__":
    main()
