# Longhorn v1.12.0

Distributed block storage for Kubernetes. Provides dynamic PVC provisioning backed by node-local disk, with replication across nodes when multiple are available.

Docs: https://longhorn.io/docs/1.12.0/deploy/install/install-with-helm/

---

## What it runs

Installed into the `longhorn` namespace. Key components:

- `longhorn-manager` — runs on every node, manages volumes and replicas
- `longhorn-driver-deployer` — installs the CSI driver
- `longhorn-ui` — web dashboard
- `csi-*` pods — handles PVC attach, detach, resize, snapshot

Data is stored at `/var/lib/longhorn/` on each node.

---

## Prerequisites (each node)

```bash
# Required by Longhorn
sudo apt install open-iscsi nfs-common -y
sudo systemctl enable iscsid && sudo systemctl start iscsid

# Prevent multipathd from interfering with Longhorn volumes
sudo tee /etc/multipath.conf <<EOF
defaults {
    user_friendly_names yes
}
blacklist {
    devnode "^sd[a-z0-9]+"
}
EOF
sudo systemctl restart multipathd

# Single-node cluster only — remove control-plane taint so pods can schedule
kubectl taint node <node-name> node-role.kubernetes.io/control-plane:NoSchedule-
```

---

## Install

```bash
helm repo add longhorn https://charts.longhorn.io
helm repo update

helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --create-namespace \
  --version 1.12.0
```

---

## Verify

```bash
kubectl get pods -n longhorn
kubectl get storageclass
# longhorn should be listed as (default)
```

---

## Access the UI

Port-forward to your local machine:

```bash
kubectl port-forward svc/longhorn-frontend 8080:80 -n longhorn
```

Open: http://localhost:8080

---

## When Node 2 joins the cluster

Longhorn detects the new node automatically. To enable replication:

1. Open the UI → Settings → Default Replica Count → set to `2`
2. Longhorn will replicate existing volumes to the new node in the background

---

## To view longhorn UI in grafana apply the following servicemonitor yaml
```base
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: longhorn-prometheus-servicemonitor
  namespace: longhorn-system
  labels:
    <whatever the 'prometheus' serviceMonitorSelector label is>
spec:
  selector:
    matchLabels:
      app: longhorn-manager
  namespaceSelector:
    matchNames:
    - longhorn-system
  endpoints:
  - port: manager

```

## Upgrade

```bash
helm upgrade longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --version <new-version>
```

## Uninstall

```bash
helm uninstall longhorn --namespace longhorn-system
kubectl delete namespace longhorn-system
```

> Uninstalling Longhorn will delete all volumes and data. Back up first.
