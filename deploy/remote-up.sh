#!/bin/bash
set -euo pipefail
for i in $(seq 1 60); do
  if command -v docker >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
cd /opt/thyme
sudo docker compose up -d --build
sudo docker compose ps
