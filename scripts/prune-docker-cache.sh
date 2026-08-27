#!/bin/sh
set -eu

# BuildKit cache is disposable but can grow by several gigabytes during rapid
# release work. Keep the last 24 hours warm and leave images, containers and
# volumes untouched.
before=$(df --output=pcent / | tail -n 1 | tr -d ' %')
docker builder prune --all --force --filter until=24h >/dev/null
after=$(df --output=pcent / | tail -n 1 | tr -d ' %')
echo "docker build cache pruned: root usage ${before}% -> ${after}%"
