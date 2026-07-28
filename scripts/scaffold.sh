#!/usr/bin/env bash
set -euo pipefail
SERVICES="identity profile catalog order wallet review trading forum festival media notification"
for s in $SERVICES; do
  mkdir -p "services/$s/app"/{domain,application,adapters,infrastructure} "services/$s/tests"
  for d in domain application adapters infrastructure; do touch "services/$s/app/$d/__init__.py"; done
  touch "services/$s/app/__init__.py"
  sed "s/_template/$s/g" services/_template/app/main.py   > "services/$s/app/main.py"
  sed "s/_template/$s/g" services/_template/app/worker.py > "services/$s/app/worker.py"
  sed "s/_template/$s/g" services/_template/Dockerfile    > "services/$s/Dockerfile"
done
echo "scaffolded: $SERVICES"
