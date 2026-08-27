# Internal DNS Server

Internal DNS server for the homelab using [CoreDNS](https://coredns.io/) deployed on Kubernetes and exposed to the LAN through MetalLB.

The purpose of this service is to provide DNS resolution for internal applications without requiring `/etc/hosts` entries on every machine.

For example:

```
pgadmin.internal.dna-server.com
        ↓
    10.0.0.71
```

Public DNS remains managed by Cloudflare. CoreDNS is only responsible for internal DNS records. (Not even gonna try to maintain a WAN DNS)

---


There are two CoreDNS deployments in the cluster:

```
kube-system
└── CoreDNS
    └── Kubernetes cluster DNS
        *.svc.cluster.local

dns
└── coredns-internal
    └── Homelab/LAN DNS
        *.internal.dna-server.com
```

The existing Kubernetes CoreDNS deployment is **not** modified.

---

## Prerequisites (Check out dnaserver-edge-stack to configure metallb)

- Kubernetes cluster
- Helm
- MetalLB
  - Existing MetalLB `IPAddressPool`
  - Existing MetalLB `L2Advertisement`
- A free IP address from the LAN subnet
- A domain/subdomain for internal DNS records

Example values used throughout this doc:

```
LAN subnet:       10.0.0.0/24
CoreDNS IP:       10.0.0.72
Nginx IP:         10.0.0.71
Internal domain:  internal.dna-server.com
```

---

## 1. Create the DNS Namespace

CoreDNS is deployed as a normal Kubernetes application rather than replacing the existing Kubernetes DNS service.

```bash
kubectl create namespace dns
```

Verify:

```bash
kubectl get namespaces
```

---

## 2. Configure MetalLB

A dedicated IP from the MetalLB address pool is used for CoreDNS.

```
10.0.0.72
```


## 3. Add the CoreDNS Helm Repository

```bash
helm repo add coredns https://coredns.github.io/helm
helm repo update
helm search repo coredns
```

---

## 4. Create CoreDNS Values (check values.yaml)

Create `values.yaml`:

```yaml
isClusterService: false

replicaCount: 2

serviceType: LoadBalancer

service:
  loadBalancerIP: 10.0.0.72

servers:
  - zones:
      - zone: .
    port: 53
    plugins:
      - name: errors
      - name: health
      - name: ready
      - name: hosts
        parameters: /etc/coredns/hosts
      - name: reload
      - name: cache
```

> **Important**
> The key setting is `isClusterService: false`. This tells the CoreDNS Helm chart that this is an external DNS service, rather than the Kubernetes cluster DNS service.


---

## 5. Install CoreDNS

```bash
helm install coredns-internal coredns/coredns \
  --namespace dns \
  -f values.yaml
```

Check the release:

```bash
helm list -n dns
```

Expected:

```
NAME               NAMESPACE   STATUS
coredns-internal   dns         deployed
```

---

## 6. Verify the CoreDNS Pods

```bash
kubectl get pods -n dns
```

Expected:

```
NAME                               READY   STATUS
coredns-internal-xxxxxxxxxx-xxxxx  1/1     Running
coredns-internal-xxxxxxxxxx-xxxxx  1/1     Running
```

Two replicas are used (`replicaCount: 2`) to provide basic redundancy.

---

## 7. Verify the CoreDNS Service

```bash
kubectl get svc -n dns
```

Expected:

```
NAME               TYPE           EXTERNAL-IP   PORT(S)
coredns-internal   LoadBalancer   10.0.0.72     ...
```

The important values are:

```
TYPE          LoadBalancer
EXTERNAL-IP   10.0.0.72
```

CoreDNS should expose DNS on UDP 53 and TCP 53. DNS normally uses UDP, but TCP is also required for some DNS responses and operations.


---

## Testinggggggg

## Manually Testing a CoreDNS Record

For initial testing, the CoreDNS ConfigMap can be edited directly.

Find the ConfigMap:

```bash
kubectl get configmap -n dns
```

Edit it:

```bash
kubectl edit configmap coredns-internal -n dns
```

The Corefile can contain an inline `hosts` configuration such as:

```
.:53 {
    errors
    health
    ready

    hosts {
        10.0.0.71 pgadmin.internal.dna-server.com
        fallthrough
    }

    reload
    cache
}
```

Save and exit, then verify the pods:

```bash
kc rollout restart deployment coredns-internal -n dns
kubectl get pods -n dns
```

---

## Test DNS From Inside Kubernetes

Run a temporary DNS test pod:

```bash
kubectl run dns-test --rm -it \
  --image=busybox:1.36 \
  --restart=Never \
  -- sh
```

Inside the container:

```bash
nslookup pgadmin.internal.dna-server.com 10.0.0.72
```


---

## Configure the Laptop to Use CoreDNS

Testing CoreDNS directly with:

```bash
nslookup pgadmin.internal.dna-server.com 10.0.0.72
```

only tests the specified DNS server. Normal applications such as `curl` and browsers use the operating system's configured DNS resolver.

Therefore, this:

```bash
curl http://pgadmin.internal.dna-server.com/login
```

will only work if the laptop's normal DNS configuration uses CoreDNS.

---

## Suppose configured DNS setting doesnt work from the GUI 

## NetworkManager Configuration

On Linux systems using NetworkManager, check the connection:

```bash
nmcli connection show
```

Check the configured IPv4 DNS:

```bash
nmcli connection show "<CONNECTION_NAME>" | grep ipv4.dns
```

Set CoreDNS as the IPv4 DNS server:

```bash
sudo nmcli connection modify "<CONNECTION_NAME>" \
  ipv4.dns "10.0.0.72"
```

Prevent automatically supplied IPv4 DNS servers from being used:

```bash
sudo nmcli connection modify "<CONNECTION_NAME>" \
  ipv4.ignore-auto-dns yes
```

Reconnect:

```bash
nmcli connection down "<CONNECTION_NAME>"
nmcli connection up "<CONNECTION_NAME>"
```