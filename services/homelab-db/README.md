# homelab-db

Helm chart that bundles **PostgreSQL** (via CloudNativePG) and **pgAdmin** for a homelab Kubernetes cluster with Longhorn storage.

---

## What this chart deploys

### PostgreSQL (CloudNativePG)
- CloudNativePG operator (subchart) installed into `cnpg-system` namespace
- A `Cluster` CR that creates 2 Postgres instances (1 primary + 1 replica)
- A `Secret` containing the DB credentials, read by the operator on first boot to create the database user
- Storage backed by Longhorn PVCs (one per instance, auto-provisioned)
- Three services created automatically by the operator:
  - `postgres-rw` — primary, read/write (use this for your apps)
  - `postgres-ro` — replica, read only
  - `postgres-r` — round-robin across all instances

### pgAdmin
- A `Deployment` running the pgAdmin 4 web UI
- A `Secret` containing the pgAdmin login email and password
- A `PVC` (1Gi) to persist server registrations and settings across restarts
- A `Service` exposing pgAdmin internally
- An `Ingress` routing `pgadmin.dnaserver.local` to the pgAdmin service via ingress-nginx

---

## Prerequisites

- Kubernetes cluster with kubectl configured
- Helm 3.x
- Longhorn installed and set as default storage class
- ingress-nginx installed

---

## Install

### 1. Add the CloudNativePG Helm repo

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm repo update
```

### 2. Pull chart dependencies

```bash
helm dependency update ./homelab-db
```

### 3. Install cnpg
```bash
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace
```

### 4. Create your overrides file

Create `values.override.yaml` next to the chart folder — this is gitignored by default:

```yaml
cluster:
  credentials:
    password: "your-postgres-password"

pgadmin:
  password: "your-pgadmin-password"
```
NOTE: Use values.yaml as a reference to create values.override.yaml

### 4. Install the chart

```bash
helm install homelab-db ./homelab-db \
  --namespace database \
  --create-namespace \
  -f values.override.yaml
```

---

## Verify

```bash
# PostgreSQL cluster health
kubectl get cluster -n database

# All pods running
kubectl get pods -n database

# PVCs bound
kubectl get pvc -n database
```

Healthy cluster output:
```
NAME       INSTANCES   READY   STATUS                     PRIMARY
postgres   2           2       Cluster in healthy state   postgres-1
```

---

## Access pgAdmin

Port-forward to your local machine:

```bash
kubectl port-forward svc/homelab-db-pgadmin 8080:80 -n database
```

Open **http://localhost:8080** and log in with:
- **Email:** your pgAdmin email from `values.override.yaml`
- **Password:** your pgAdmin password from `values.override.yaml`

Then register the Postgres server in pgAdmin (Servers → Register → Server):

| Field    | Value |
|----------|-------|
| Host     | `postgres-rw.database.svc.cluster.local` |
| Port     | `5432` |
| Database | `appdb` |
| Username | `app` |
| Password | your postgres password |

---

## Upgrade

```bash
helm upgrade homelab-db ./homelab-db \
  --namespace database \
  -f values.override.yaml
```

## Uninstall

```bash
helm uninstall homelab-db --namespace database
```

PVCs are preserved on uninstall to protect your data. To fully remove:

```bash
kubectl delete pvc -n database --all
```