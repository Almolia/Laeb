# Laeb Kubernetes bonus

These manifests map the Docker Compose topology to namespace `laeb`.

## Contents

- shared ConfigMap and Secret;
- PostgreSQL, MongoDB, Redis, RabbitMQ, and MinIO with PVCs where needed;
- two API replicas, resource requests/limits, `/health` liveness, and `/ready`
  readiness for every microservice;
- one worker deployment per service;
- path-based Ingress matching `/api/v1/<service>`;
- Catalog HPA from 2 to 10 replicas at 70% average CPU.

## Why Catalog gets the HPA

NFR-01 predicts store traffic spikes during festivals while forum traffic stays
steadier. Catalog is read-heavy and owns browsing/effective-price queries, so it
must scale independently from write-heavy Wallet and the other services. The HPA
is placed on Catalog rather than scaling the complete platform as one unit.

## Apply

Build/tag images as `laeb/<service>:latest` and load them into kind or make them
available to the cluster. Then:

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/ -R
kubectl -n laeb get pods
kubectl -n laeb get hpa catalog
```

Validation without a cluster:

```bash
kubectl apply --dry-run=client -f deploy/k8s/ -R
```

The included Secret contains base64-encoded **development-only** values.
Production must use an external secret manager or sealed-secret workflow and
must not commit real credentials.
