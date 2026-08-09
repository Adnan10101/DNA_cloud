# Post-reboot health check

Run through this in order after both nodes are back up. Each section
builds on the one before it -- no point checking ingress if kube-system
itself isn't healthy yet.

## 1. Nodes themselves

```bash
kubectl get nodes -o wide
```
Both should show `STATUS: Ready`. If a node shows `NotReady`, check:
```bash
kubectl describe node <node-name>
```
Look at the `Conditions` section (`MemoryPressure`, `DiskPressure`,
`PIDPressure`, `Ready`) and `Events` at the bottom.

## 2. kube-system core components

```bash
kubectl get pods -n kube-system -o wide
```
Everything should be `Running`, `0` or low `RESTARTS`. Specifically check:
- `etcd-*` -- both nodes' copies healthy (if you run etcd on both)
- `kube-apiserver-*`
- `kube-controller-manager-*` (control-plane node only, per your setup)
- `kube-scheduler-*` (control-plane node only)
- `kube-proxy-*` -- one per node

If any are `CrashLoopBackOff`:
```bash
kubectl logs -n kube-system <pod-name> --previous
```

## 3. Calico (CNI / pod networking)

Nothing else works right if this isn't healthy -- check it right after
kube-system, before anything app-level.

```bash
kubectl get pods -n calico-system -o wide
```
All `calico-node-*` (one per node), `calico-kube-controllers-*`,
`calico-typha-*` should be `Running`.

Check Calico's own view of node status:
```bash
kubectl exec -n calico-system -it $(kubectl get pods -n calico-system -l k8s-app=calico-node -o jsonpath='{.items[0].metadata.name}') -- calico-node -bird-ready
```

Quick cross-node pod connectivity sanity check (proves the overlay network
actually works, not just that pods are Running):
```bash
kubectl run net-test --image=busybox --rm -it --restart=Never -- ping -c3 <ip-of-a-pod-on-the-other-node>
```

## 4. CoreDNS (in-cluster DNS)

Easy to forget, but everything (Services, Ingress backends) depends on it
resolving correctly.

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
```
Test resolution from inside the cluster:
```bash
kubectl run dns-test --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default
```

## 5. Longhorn (storage)

```bash
kubectl get pods -n longhorn-system -o wide
```
All manager/driver/UI pods `Running`. Then check volume health specifically
(this is the part that can take a few minutes to settle after a reboot):
```bash
kubectl get volumes.longhorn.io -n longhorn-system
```
Look at the `STATE` and `ROBUSTNESS` columns -- want `attached`/`healthy`.
`degraded` is normal briefly after reboot (resyncing replicas); give it a
few minutes and recheck. `faulted` needs investigation via the Longhorn UI.

## 6. MetalLB + both ingress-nginx controllers

```bash
kubectl get pods -n metallb-system -o wide
kubectl get svc -n ingress-nginx
kubectl get svc -n ingress-nginx-internal
```
Both Services' `EXTERNAL-IP` should show their assigned IPs (`10.0.0.70`,
`10.0.0.71`), not `<pending>`.

```bash
kubectl get pods -n ingress-nginx -o wide
kubectl get pods -n ingress-nginx-internal -o wide
```
Confirm 2 pods each, on different nodes (anti-affinity holding).

## 7. WireGuard tunnel (Linode side + home node side)

On the home node with the tunnel:
```bash
sudo wg show
```
Check `latest handshake` is recent (within the last couple minutes).

```bash
systemctl is-enabled wg-quick@wg0
systemctl is-active wg-quick@wg0
```
If not enabled/active, `sudo systemctl enable --now wg-quick@wg0`.

## 8. IP forwarding + iptables rules (home node)

These don't persist by default -- confirmed known TODO. Check they're
actually still in place after reboot:
```bash
cat /proc/sys/net/ipv4/ip_forward   # should print 1
sudo iptables -L FORWARD -v
```
If the FORWARD rules are gone, re-add them (or better -- finally set up
`iptables-persistent` so this stops being a manual step every time):
```bash
sudo iptables -A FORWARD -i wg0 -o eth0 -j ACCEPT
sudo iptables -A FORWARD -i eth0 -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT
```

## 9. CloudNativePG / Postgres

```bash
kubectl get pods -n nextcloud   # or wherever your Cluster CR lives
kubectl get cluster.postgresql.cnpg.io -A
```
Check the `STATUS` column shows healthy/running, not `Failed` or stuck
`Initializing`.

## 10. Alertmanager / Prometheus / Grafana

```bash
kubectl get pods -n monitoring -o wide
```
Then confirm the generated Alertmanager config is still intact (it's a
Secret, survives fine, but worth a sanity check after any control-plane
hiccup):
```bash
kubectl get alertmanager -n monitoring
# RECONCILED should be True
```

## 11. End-to-end test (the real proof)

From Linode:
```bash
curl -I -H "Host: grafana.dna-server.com" http://10.0.0.70
```
From a LAN device:
```bash
curl -I -H "Host: pgadmin.internal.dna-server.com" http://10.0.0.71
```
Both should return normal `302`/`200` responses, same as always.

---

## If something's still wrong after all of this

Check the Prometheus Operator logs -- it's often the fastest way to see a
clear error message rather than guessing:
```bash
kubectl logs -n monitoring -l app.kubernetes.io/name=kube-prometheus-stack-prometheus-operator --tail=100
```

And Calico's, if networking is the suspect:
```bash
kubectl logs -n calico-system -l k8s-app=calico-node --tail=100
```