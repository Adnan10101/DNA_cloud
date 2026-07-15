# Homelab Kubernetes — Monitoring Stack Guide

A complete reference for setting up and operating the monitoring stack on a Kubernetes homelab cluster.

---

## Table of Contents

1. [Stack Overview](#stack-overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Accessing the Tools](#accessing-the-tools)
5. [Grafana — Dashboards & Visualization](#grafana--dashboards--visualization)
6. [Prometheus — Metrics](#prometheus--metrics)
7. [Loki — Logs](#loki--logs)
8. [Alerting](#alerting)
9. [Longhorn Dashboard](#longhorn-dashboard)
10. [Troubleshooting](#troubleshooting)
11. [Useful Commands](#useful-commands)

---

## Stack Overview

```
K8s cluster
    │
    ├── Node Exporter        → hardware metrics (CPU, RAM, disk, network)
    ├── kube-state-metrics   → Kubernetes object metrics (pod health, deployments)
    ├── Longhorn metrics     → storage capacity and volume health
    ├── Promtail             → collects logs from every pod on every node
    │
    ▼
Prometheus (stores all metrics)     Loki (stores all logs)
    │                                    │
    └──────────────┬─────────────────────┘
                   │
                Grafana (visualizes everything)
                   │
             Alertmanager (notifies you)
                   
```

### What Each Tool Does

| Tool | What it does  |
|---|---|---|
| Prometheus | Records metrics from your cluster every 15 seconds |
| Grafana | Draws those metrics as graphs and dashboards | 
| Alertmanager | Notifies you when metrics cross thresholds |
| Node Exporter | Reports hardware stats from each physical node | 
| kube-state-metrics | Reports Kubernetes object health | 
| Loki | Stores and searches logs from every pod |
| Promtail | Collects logs from nodes and ships to Loki | 

### Metrics vs Logs

```
Metrics (Prometheus + Grafana)     Logs (Loki)
────────────────────────────────   ───────────────────────────────
Numbers over time                  Text events over time
"CPU is at 90%"                    "ERROR: connection refused"
"Pod restarted 5 times"            "FATAL: out of memory"
Tells you SOMETHING IS WRONG       Tells you WHY it went wrong
```

---

## Prerequisites

- A running Kubernetes cluster
- Longhorn installed and storage class available
- Helm installed

```bash
# Verify before starting
kubectl get nodes                    # both Ready
kubectl get storageclass             # longhorn listed
helm version                         # helm installed
```

---

## Installation

### Step 1 — kube-prometheus-stack

Installs Prometheus, Grafana, Alertmanager, Node Exporter, and kube-state-metrics in one chart.

```bash
helm repo add prometheus-community \
  https://prometheus-community.github.io/helm-charts
helm repo update
```

Create values file:

```bash
cat << 'EOF' > monitoring-values.yaml
grafana:
  adminPassword: "changeme"
  persistence:
    enabled: true
    storageClassName: longhorn
    size: 5Gi

prometheus:
  prometheusSpec:
    retention: 15d
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: longhorn
          resources:
            requests:
              storage: 20Gi

alertmanager:
  alertmanagerSpec:
    storage:
      volumeClaimTemplate:
        spec:
          storageClassName: longhorn
          resources:
            requests:
              storage: 2Gi
EOF
```

Install:

```bash
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  -f monitoring-values.yaml

# Watch pods come up — wait until all Running
kubectl get pods -n monitoring -w
```

Expected pods when healthy:

```
alertmanager-monitoring-kube-prometheus-alertmanager-0   2/2   Running
monitoring-grafana-xxx                                   3/3   Running
monitoring-kube-prometheus-operator-xxx                  1/1   Running
monitoring-kube-state-metrics-xxx                        1/1   Running
monitoring-prometheus-node-exporter-xxx                  1/1   Running  (one per node)
prometheus-monitoring-kube-prometheus-prometheus-0       2/2   Running
```

---

### Step 2 — Loki

Installs Loki (log storage) and Promtail (log collector).

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set loki.image.tag=2.9.3 \
  --set loki.persistence.enabled=true \
  --set loki.persistence.storageClassName=longhorn \
  --set loki.persistence.size=10Gi \
  --set promtail.enabled=true

kubectl get pods -n monitoring -w
```

>  **Version note:** Always set `loki.image.tag=2.9.3` or newer.

Expected pods when healthy:

```
loki-0              1/1   Running
loki-promtail-xxx   1/1   Running  (one per node, so 2 total)
```

---

### Step 3 — Connect Loki to Grafana

```
Grafana → Connections → Data Sources → Add new data source
Type: Loki
URL: http://loki:3100
Default: OFF  ← important, do not mark as default
Save & Test → should say "Data source connected"
```

---

### Step 4 — Enable Longhorn Metrics (TBD)

Prometheus needs a ServiceMonitor to know where to scrape Longhorn metrics:

```bash
kubectl apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: longhorn-prometheus-servicemonitor
  namespace: longhorn-system
  labels:
    release: monitoring
spec:
  selector:
    matchLabels:
      app: longhorn-manager
  namespaceSelector:
    matchNames:
      - longhorn-system
  endpoints:
  - port: manager
    path: /metrics
EOF
```

Verify Prometheus is scraping Longhorn:

```bash
kubectl port-forward -n monitoring \
  svc/monitoring-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/targets
# Look for longhorn — should show UP
```

---

## Accessing the Tools (TBD)

All tools are accessed via port-forward. Need to set up ingress later for permanent URLs.

```bash
# Grafana (main UI — use this most of the time)
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
# http://localhost:3000  |  admin / changeme

# Prometheus (raw metrics and targets)
kubectl port-forward -n monitoring \
  svc/monitoring-kube-prometheus-prometheus 9090:9090
# http://localhost:9090

# Alertmanager (active alerts and silences)
kubectl port-forward -n monitoring \
  svc/monitoring-kube-prometheus-alertmanager 9093:9093
# http://localhost:9093
```

---

## Grafana — Dashboards & Visualization

### Pre-built Dashboards (Available Immediately)

Navigate to Grafana → Dashboards to find these out of the box:

| Dashboard | What it shows |
|---|---|
| Kubernetes / Cluster Overview | All nodes, pods, resource usage |
| Kubernetes / Node Exporter | Per-node CPU, RAM, disk, network |
| Kubernetes / Workloads | Per-namespace pod health |
| Kubernetes / Persistent Volumes | PVC usage and capacity |
| Alertmanager | Active alerts |

### Import Longhorn Dashboard

```
Grafana → Dashboards → New → Import
Dashboard ID: 13032
Data source: Prometheus
Import
```

> Dashboard IDs come from grafana.com/grafana/dashboards — a public library of community dashboards. `13032` is the official Longhorn dashboard.

### Exploring Logs with Loki

```
Grafana → Explore → Select Loki as data source

Useful queries:
{namespace="longhorn-system"}              → all Longhorn logs
{namespace="monitoring"}                   → all monitoring logs
{namespace="longhorn-system"} |= "error"   → errors only
{pod="loki-0"}                             → specific pod logs
```

---

Note: Apply all the alerts under alerts/ after setting up prometheus/grafana. 


## Useful Commands

### Health Checks

```bash
# All monitoring pods healthy?
kubectl get pods -n monitoring

# PVCs all bound?
kubectl get pvc -n monitoring

# Check Prometheus targets
kubectl port-forward -n monitoring \
  svc/monitoring-kube-prometheus-prometheus 9090:9090
# Then visit http://localhost:9090/targets
```

### Helm Management

```bash
# Check installed releases
helm list -n monitoring

# Upgrade monitoring stack
helm upgrade monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  -f monitoring-values.yaml

# Upgrade Loki
helm upgrade loki grafana/loki-stack \
  --namespace monitoring \
  --set loki.image.tag=2.9.3 \
  --set loki.persistence.enabled=true \
  --set loki.persistence.storageClassName=longhorn \
  --set loki.persistence.size=10Gi \
  --set promtail.enabled=true

# Uninstall everything
helm uninstall monitoring -n monitoring
helm uninstall loki -n monitoring
```

### Get Grafana Admin Password

```bash
kubectl get secret -n monitoring monitoring-grafana \
  -o jsonpath="{.data.admin-password}" | base64 -d && echo
```

---

