#!/bin/sh
# Local/root checks on the VPS. Also run fresh public/tunnel SSH and off-host
# probes from the runbook: established sessions cannot prove new access works.
set -eu
systemctl is-active --quiet anicast-firewall.service
systemctl is-enabled --quiet anicast-firewall.service
python3 - <<'PY'
import json
import subprocess

data = json.loads(subprocess.check_output(["nft", "-j", "list", "table", "inet", "anicast_edge"], text=True))
chains = {x["chain"]["name"]: x["chain"] for x in data["nftables"] if "chain" in x}
assert chains["input"]["policy"] == "drop"
assert chains["input"]["prio"] == -10
assert chains["forward"]["prio"] == -10
subprocess.run(["nft", "list", "table", "ip", "anicast_awg_nat"], check=True, stdout=subprocess.DEVNULL)
subprocess.run(["iptables", "-C", "FORWARD", "-j", "DOCKER-USER"], check=True)
print("Firewall enabled: INPUT drop, pre-Docker filter, AWG NAT and Docker chains present")
PY
