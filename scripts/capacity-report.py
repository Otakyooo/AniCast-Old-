#!/usr/bin/env python3
"""Read bounded host history from the existing private Prometheus; no writes."""

import argparse
import datetime as dt
import json
import math
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen


JOBS = {"node": "MainServer", "node-vps": "VPS"}
SELECTOR = '{job=~"node|node-vps"}'
STEP = 300
QUERIES = {
    "scrape_up": "up" + SELECTOR,
    "memory_total_mib": "node_memory_MemTotal_bytes" + SELECTOR + " / 1048576",
    "memory_available_mib": "node_memory_MemAvailable_bytes" + SELECTOR + " / 1048576",
    "memory_available_percent": "100 * node_memory_MemAvailable_bytes" + SELECTOR
    + " / node_memory_MemTotal_bytes" + SELECTOR,
    "cpu_busy_percent_5m": '100 * (1 - avg by (job) (rate(node_cpu_seconds_total'
    '{job=~"node|node-vps",mode="idle"}[5m])))',
    "cpu_iowait_percent_5m": '100 * avg by (job) (rate(node_cpu_seconds_total'
    '{job=~"node|node-vps",mode="iowait"}[5m]))',
    "swap_in_pages_per_second_5m": "rate(node_vmstat_pswpin" + SELECTOR + "[5m])",
    "swap_out_pages_per_second_5m": "rate(node_vmstat_pswpout" + SELECTOR + "[5m])",
}


def summarize(points, expected):
    """Missing/NaN samples remain missing, never become zero load."""
    values = [float(value) for _, value in points if math.isfinite(float(value))]
    if not values:
        return {"samples": 0, "coverage_percent": 0.0}
    ordered = sorted(values)
    return {
        "samples": len(values),
        "coverage_percent": round(100 * len(values) / expected, 2),
        "min": round(ordered[0], 3),
        "p95": round(ordered[math.ceil(0.95 * len(ordered)) - 1], 3),
        "max": round(ordered[-1], 3),
        "latest": round(values[-1], 3),
    }


def query(expression, start, end):
    params = urlencode({"query": expression, "start": start, "end": end, "step": STEP})
    with urlopen("http://127.0.0.1:9090/api/v1/query_range?" + params, timeout=20) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Prometheus response exceeds bounded report size")
    payload = json.loads(raw)
    if payload.get("status") != "success" or payload.get("warnings"):
        raise ValueError("Prometheus query failed or returned warnings")
    if payload["data"]["resultType"] != "matrix":
        raise ValueError("Expected Prometheus range matrix")
    return payload["data"]["result"]


def collect(hours, end, fetch=query):
    start = end - hours * 3600
    expected = (end - start) // STEP + 1
    report = {
        "start_utc": dt.datetime.fromtimestamp(start, dt.timezone.utc).isoformat(),
        "end_utc": dt.datetime.fromtimestamp(end, dt.timezone.utc).isoformat(),
        "step_seconds": STEP,
        "expected_samples_per_signal": expected,
        "hosts": {name: {} for name in JOBS.values()},
    }
    for name, expression in QUERIES.items():
        seen = set()
        for series in fetch(expression, start, end):
            job = series["metric"]["job"]
            if job not in JOBS or job in seen:
                raise ValueError("Expected exactly one series per configured host and signal")
            seen.add(job)
            report["hosts"][JOBS[job]][name] = summarize(series["values"], expected)
        for job in JOBS:
            if job not in seen:
                report["hosts"][JOBS[job]][name] = summarize([], expected)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, choices=range(1, 73), default=24, metavar="1..72")
    args = parser.parse_args()
    try:
        report = collect(args.hours, int(time.time()))
    except Exception as error:
        # Do not dump HTTP bodies or exception strings into operational logs.
        print("Capacity report failed: " + type(error).__name__, file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        "Five-minute samples; CPU/swap use five-minute rates. Coverage is sampled "
        "history presence, not uptime. Missing data is not zero load. Scrape up=0 "
        "means exporter failure. Historical maxima include maintenance; this is "
        "not a load test or a guarantee of peak capacity.",
        file=sys.stderr,
    )
    return 0 if all(
        signal["samples"] for host in report["hosts"].values() for signal in host.values()
    ) else 2


if __name__ == "__main__":
    sys.exit(main())
