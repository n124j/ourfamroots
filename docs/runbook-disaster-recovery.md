# OurFamRoots — Disaster Recovery Runbook

**RTO target:** 1 hour | **RPO target:** 24 hours (daily backup)

---

## 1. Database failure (PostgreSQL down)

### Symptoms
- `PostgresDown` alert fires in Alertmanager
- API pods returning 503 / 500

### Steps

```bash
# 1. Check pod status
kubectl get pods -n ourfamroots -l app=postgres

# 2. Describe the failing pod
kubectl describe pod <pod-name> -n ourfamroots

# 3. Check PVC availability
kubectl get pvc -n ourfamroots

# 4. Force pod restart
kubectl rollout restart deployment/postgres -n ourfamroots
```

If data is corrupt, restore from backup:

```bash
# List available backups
aws s3 ls s3://${S3_BUCKET}/backups/postgres/ --recursive | sort -r | head -20

# Download latest backup
aws s3 cp s3://${S3_BUCKET}/backups/postgres/<DATE>.dump /tmp/restore.dump

# Restore (drops and recreates the DB)
kubectl exec -it deploy/postgres -n ourfamroots -- \
  bash -c "dropdb ourfamroots && createdb ourfamroots"

kubectl exec -i deploy/postgres -n ourfamroots -- \
  pg_restore --dbname=ourfamroots --no-owner --no-acl /dev/stdin < /tmp/restore.dump

# Run Alembic migrations to bring schema to HEAD
kubectl exec deploy/api-blue -n ourfamroots -- alembic upgrade head
```

---

## 2. Redis failure

### Symptoms
- `RedisDown` alert fires
- Auth token refresh failures; Celery tasks queuing up

### Steps

```bash
# Restart Redis
kubectl rollout restart deployment/redis -n ourfamroots

# Verify connectivity
kubectl exec -it deploy/redis -n ourfamroots -- redis-cli ping
```

Redis is an ephemeral cache + Celery broker. No data restore needed — sessions will re-authenticate and tasks will re-queue automatically.

---

## 3. Failed blue/green deployment

### Symptoms
- `HighErrorRate` alert fires shortly after a deploy
- New slot shows failures during smoke test

### Steps (manual rollback)

```bash
# Identify which slot is currently live
kubectl get svc api -n ourfamroots -o jsonpath='{.spec.selector.slot}'

# Roll traffic back to old slot (replace OLD_SLOT with blue or green)
kubectl patch svc api -n ourfamroots \
  -p '{"spec":{"selector":{"app":"api","slot":"OLD_SLOT"}}}'
kubectl patch svc frontend -n ourfamroots \
  -p '{"spec":{"selector":{"app":"frontend","slot":"OLD_SLOT"}}}'

# Scale down the failed new slot
kubectl scale deployment api-NEW_SLOT --replicas=0 -n ourfamroots
kubectl scale deployment frontend-NEW_SLOT --replicas=0 -n ourfamroots

echo "Rollback complete"
```

CI auto-rollback handles this automatically for pipeline failures. Manual steps above are for production incidents discovered after traffic switch.

---

## 4. Full cluster loss

1. Provision new K8s cluster (EKS/GKE/AKS)
2. Install prerequisites:
   ```bash
   helm repo add jetstack https://charts.jetstack.io
   helm install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace \
     --set installCRDs=true

   helm repo add kedacore https://kedacore.github.io/charts
   helm install keda kedacore/keda --namespace keda --create-namespace
   ```
3. Apply sealed secrets or re-create `ourfamroots-secrets`
4. Install the Helm chart:
   ```bash
   helm upgrade --install ourfamroots ./helm/ourfamroots \
     --namespace ourfamroots --create-namespace \
     --set image.tag=<LAST_KNOWN_GOOD_TAG>
   ```
5. Restore the database from S3 (see section 1)
6. Validate with smoke tests:
   ```bash
   curl https://api.ourfamroots.example.com/health
   ```

---

## 5. Contacts

| Role | Contact |
|------|---------|
| On-call | PagerDuty — OurFamRoots service |
| Infrastructure | #infra-ops Slack |
| Database | DBA team |
| Security incident | security@example.com |

---

## 6. Backup verification schedule

Run monthly:

```bash
# Download a recent backup and restore to a test DB
aws s3 cp s3://${S3_BUCKET}/backups/postgres/<LATEST>.dump /tmp/test-restore.dump

docker run --rm -e POSTGRES_PASSWORD=test postgres:15-alpine \
  bash -c "initdb /tmp/pgtest && pg_ctl start -D /tmp/pgtest && \
           createdb testdb && \
           pg_restore --dbname=testdb /dev/stdin" < /tmp/test-restore.dump

echo "Backup verified ✓"
```
