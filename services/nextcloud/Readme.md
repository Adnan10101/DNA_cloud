# Nextcloud

Self-hosted file storage/sync, my personal Drive equivalent!

## Why an existing Postgres instance, not a dedicated one

Nextcloud uses its own **database**
inside the already-running `homelab-db` instance. 

---

## 1. Create the Nextcloud database

Currently using the Postgres **superuser** - will need to change this in the future

Via pgAdmin:
Right-click **Databases → Create → Database** → Database: `nextcloud`,
Owner: `postgres`.

Or via `psql` directly in the Postgres pod:
```bash
kubectl exec -it postgres-1 -n database -- psql -h 127.0.0.1 -U postgres
```
```sql
CREATE DATABASE nextcloud;
```

## 2. Namespace + DB credentials Secret

```bash
kubectl create namespace nextcloud

kubectl create secret generic nextcloud-db-credentials \
  --from-literal=username='postgres' \
  --from-literal=password='<actual postgres password>' \
  -n nextcloud
```

Postgres user creds

## 3. Helm values

```yaml
nextcloud:
  host: files.dna-server.com
  username: admin
  password: changeme-then-rotate-in-ui   # only used on very first init -- see section 6
  configs:
    custom.config.php: |
      <?php
      $CONFIG = array(
        'trusted_domains' => array(
          $_ENV['NEXTCLOUD_TRUSTED_DOMAINS'],
        ),
      );

internalDatabase:
  enabled: false

externalDatabase:
  enabled: true
  type: postgresql
  host: postgres-rw.database.svc.cluster.local
  database: nextcloud
  existingSecret:
    enabled: true
    secretName: nextcloud-db-credentials
    usernameKey: username
    passwordKey: password

persistence:
  enabled: true
  storageClass: longhorn
  size: 100Gi

service:
  type: ClusterIP

ingress:
  enabled: false   # managed manually, matching the rest of the stack
```

**The `configs.custom.config.php` block is required, not optional.**
Without it, the pod crash-loops: kubelet's liveness/readiness probes get
rejected by Nextcloud with `400 Bad Request` because `trusted_domains`
doesn't reliably get populated from `nextcloud.host` by the chart alone.
Confirmed via a known upstream issue with the identical symptom. If probe
failures return after a chart upgrade, check this is still present. (Research done by `Claude` will need to verify this on my own)

```bash
helm repo add nextcloud https://nextcloud.github.io/helm/
helm repo update
helm upgrade --install nextcloud nextcloud/nextcloud -n nextcloud -f nextcloud-values.yaml
kubectl get pods -n nextcloud -w
```

Confirm DB connection succeeded (not just "pod Running"):
```bash
kubectl logs -n nextcloud -l app.kubernetes.io/name=nextcloud --tail=100
```

## 4. Ingress (external) + Linode nginx + DNS

Same stuff as grafana/alertmanager



## 6. Fixing the admin account after first install

`nextcloud.username`/`password` in the Helm values only apply during the
**very first** database initialization. Incase I need this in the future

Fixed via `occ` (Nextcloud's CLI, must run as `www-data`):

```bash
# check existing accounts
kubectl exec -it -n nextcloud deploy/nextcloud -- su -s /bin/bash www-data -c "php occ user:list"

# create the real admin account (prompts for password interactively)
kubectl exec -it -n nextcloud deploy/nextcloud -- su -s /bin/bash www-data -c "php occ user:add <new-user> --group='admin'"

# confirm login works with the new account BEFORE deleting the old one
kubectl exec -it -n nextcloud deploy/nextcloud -- su -s /bin/bash www-data -c "php occ user:delete <old-user>"
```

## 7. Multiple user accounts (TODO)

Nextcloud supports this natively -- no extra setup required.

- **Via UI:** profile icon → Users → New user. Set quota per user here too
  (worth doing, given the fixed-size PVC).
- **Via `occ`:** `php occ user:add <username>` (same `su -s /bin/bash
  www-data -c "..."` wrapper as above).
- **Sharing between users:** right-click any file/folder → Share → pick a
  user or group, with configurable permissions -- this is the normal way
  to give people access to specific things without a shared login.
- Self-registration is off by default (admin-created accounts only) --
  appropriate for a personal/family instance.
