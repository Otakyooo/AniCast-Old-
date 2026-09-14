#!/bin/sh
set -eu

# Resolve published GHCR images to immutable digests and print release
# manifests accepted by scripts/deploy.sh. Requires `docker login ghcr.io`
# (private packages need a token with read:packages).
#
# usage: release-manifest.sh <git-sha>
#        release-manifest.sh --tag main|v1.2.3

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
registry=${REGISTRY:-ghcr.io}
owner=${OWNER:-otakyooo}

mode=${1:-}
case "$mode" in
    --tag) ref=${2:?image tag required} ;;
    *) ref=${1:?usage: release-manifest.sh <git-sha> | --tag <tag>} ;;
esac

case "$ref" in
    *:*) suffix=$ref ;;
    *) suffix=sha-$ref ;;
esac

digest_of() {
    docker buildx imagetools inspect --format '{{.Manifest.Digest}}' "$1" | tr -d '"'
}

backend_digest=$(digest_of "$registry/$owner/anicast-backend:$suffix")
frontend_digest=$(digest_of "$registry/$owner/anicast-frontend:$suffix")
# Production keeps these beside the checkout, not under /etc. /etc/anicast
# only ever held firewall.nft, and it exists on the VPS alone.
mainserver_env=${MAINSERVER_ENV_FILE:-/home/lama_admin/anicast/infra/mainserver/.env}
vps_env=${VPS_ENV_FILE:-/opt/anicast/infra/vps/.env}

echo "# mainserver release: scripts/deploy.sh mainserver this.env"
echo "BACKEND_IMAGE=$registry/$owner/anicast-backend@$backend_digest"
echo "RELEASE_SHA=$ref"
echo "ANICAST_ENV_FILE=$mainserver_env"
echo
echo "# vps release: scripts/deploy.sh vps this.env"
echo "FRONTEND_IMAGE=$registry/$owner/anicast-frontend@$frontend_digest"
echo "RELEASE_SHA=$ref"
echo "ANICAST_ENV_FILE=$vps_env"
