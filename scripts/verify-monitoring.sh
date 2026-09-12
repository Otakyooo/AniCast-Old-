#!/bin/sh
# Run on MainServer after at least one 30-second scrape interval.
set -eu
project=${ANICAST_PROJECT_MONITORING:-monitoring}
# Check readability as the container user (65534), not as root: a root-only
# check passes on 600 root files that Prometheus/Alertmanager cannot read.
docker exec -u 65534 "$project-prometheus-1" sh -c 'test -r /etc/prometheus/secrets/metrics-token'
docker exec -u 65534 "$project-alertmanager-1" sh -c 'test -r /etc/alertmanager/secrets/telegram-token'
python3 - <<'PY'
import json
from urllib.parse import urlencode
from urllib.request import urlopen

def query(expression):
    url = "http://127.0.0.1:9090/api/v1/query?" + urlencode({"query": expression})
    with urlopen(url, timeout=5) as response:
        data = json.load(response)
    assert data["status"] == "success", "Prometheus query failed"
    return data["data"]["result"]

backend = query('up{job="anicast-backend"}')
assert backend and all(float(x["value"][1]) == 1 for x in backend), "backend scrape unavailable"
roles = query('anicast_redis_up{job="anicast-backend"}')
assert {x["metric"]["role"] for x in roles} == {"control", "ephemeral", "broker"}, "Redis signals missing"
assert all(float(x["value"][1]) == 1 for x in roles), "Redis role unavailable"
print("Monitoring verified: secret files readable, backend scraped, all three Redis roles up")
PY
