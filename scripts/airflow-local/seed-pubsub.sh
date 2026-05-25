#!/usr/bin/env bash
#
# seed-pubsub.sh — Create Pub/Sub topic and subscription in the emulator.

set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}✅ $*${NC}"; }
info() { echo -e "${YELLOW}   $*${NC}"; }

export PUBSUB_EMULATOR_HOST="${PUBSUB_EMULATOR_HOST:-localhost:8085}"
export PUBSUB_PROJECT_ID="${PUBSUB_PROJECT_ID:-local}"

TOPIC="generic-file-notifications"
SUB="generic-file-notifications-sub"
DLQ_TOPIC="generic-file-notifications-dlq"
DLQ_SUB="generic-file-notifications-dlq-sub"

PUBSUB_API="http://${PUBSUB_EMULATOR_HOST}/v1/projects/${PUBSUB_PROJECT_ID}"

log "Creating topic $TOPIC"
curl -fs -X PUT "$PUBSUB_API/topics/$TOPIC" >/dev/null 2>&1 || info "topic exists"

log "Creating topic $DLQ_TOPIC"
curl -fs -X PUT "$PUBSUB_API/topics/$DLQ_TOPIC" >/dev/null 2>&1 || info "dlq topic exists"

log "Creating subscription $SUB"
curl -fs -X PUT "$PUBSUB_API/subscriptions/$SUB" \
  -H "Content-Type: application/json" \
  -d "{\"topic\":\"projects/${PUBSUB_PROJECT_ID}/topics/${TOPIC}\",\"ackDeadlineSeconds\":60}" \
  >/dev/null 2>&1 || info "subscription exists"

log "Creating subscription $DLQ_SUB"
curl -fs -X PUT "$PUBSUB_API/subscriptions/$DLQ_SUB" \
  -H "Content-Type: application/json" \
  -d "{\"topic\":\"projects/${PUBSUB_PROJECT_ID}/topics/${DLQ_TOPIC}\",\"ackDeadlineSeconds\":60}" \
  >/dev/null 2>&1 || info "dlq subscription exists"

pass "Pub/Sub seeded."
info "Topic:         projects/${PUBSUB_PROJECT_ID}/topics/${TOPIC}"
info "Subscription:  projects/${PUBSUB_PROJECT_ID}/subscriptions/${SUB}"
