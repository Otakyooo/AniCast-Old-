#!/usr/bin/env python3
"""Short public GET probe; 36 requests, concurrency 1/2/4, never a capacity claim.

Run from the operator computer after checking capacity-report.py. Fetches HTML
and a bounded catalogue page only: no assets, video, accounts or write requests.
Stops between waves on errors or requests over 3s; each wave pauses for 1s.
"""
import concurrent.futures
import datetime as dt
import json
import math
import time
import urllib.error
import urllib.request

ORIGIN = "https://anicast.online"
PATHS = ("/", "/catalog", "/api/v1/titles/?page_size=1")


def request(path):
    started = time.monotonic()
    status, size, error = 0, 0, None
    try:
        req = urllib.request.Request(ORIGIN + path, headers={"User-Agent": "Anicast-Bounded-Read-Check/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            status = response.status
            size = len(response.read(2 * 1024 * 1024 + 1))
            if size > 2 * 1024 * 1024:
                error = "response_size_limit"
    except urllib.error.HTTPError as exc:
        status, error = exc.code, "http_error"
    except Exception as exc:
        error = type(exc).__name__
    return {"path": path, "status": status, "ms": round((time.monotonic() - started) * 1000), "bytes": size, "error": error}


def main():
    report = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "stages": [], "stopped": False}
    for concurrency in (1, 2, 4):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            for offset in range(0, 12, concurrency):
                results.extend(pool.map(request, [PATHS[i % len(PATHS)] for i in range(offset, offset + concurrency)]))
                if any(row["status"] != 200 or row["error"] or row["ms"] > 3000 for row in results):
                    report["stopped"] = True
                    break
                time.sleep(1)
        ordered = sorted(row["ms"] for row in results)
        stage = {"concurrency": concurrency, "requests": len(results), "p50_ms": ordered[math.ceil(len(ordered) * .5) - 1],
                 "p95_ms": ordered[math.ceil(len(ordered) * .95) - 1], "max_ms": max(ordered), "results": results}
        report["stages"].append(stage)
        print(json.dumps({key: value for key, value in stage.items() if key != "results"}), flush=True)
        if report["stopped"]:
            break
    print(json.dumps(report, indent=2))
    return 1 if report["stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
