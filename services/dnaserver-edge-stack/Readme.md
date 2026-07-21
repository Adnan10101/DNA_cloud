# dnaserver-edge-stack

Documents how services running in the home Kubernetes cluster (e.g. Grafana)
are exposed to the internet through Linode

## Architecture

```
Internet
  │
  ▼
Cloudflare DNS (A record → Linode public IP)
  │
  ▼
Linode (public VM)
  │  nginx reverse proxy, terminates the public-facing hostname
  │
  ▼  (WireGuard tunnel)
Home server / K8s node
  │  IP forwarding: wg0 → LAN interface
  │
  ▼
Home LAN (10.0.0.0/24)
  │  ARP resolves the floating ingress IP
  │
  ▼
MetalLB-assigned IP (10.0.0.70) → ingress-nginx (LoadBalancer Service)
  │  reads HTTP Host header, routes by hostname
  │
  ▼
Backend Service (e.g. monitoring-grafana:80) → Pod
```

**Mental note to sefl:** the ingress IP lives on the real home LAN subnet
(`10.0.0.0/24`), not the WireGuard tunnel subnet (`10.8.0.0/24`). WireGuard
interfaces are point-to-point tunnels with no broadcast domain, so they
cannot support ARP/L2 announcements. MetalLB's L2 mode requires ARP to work,
so the floating IP must sit on a network segment where ARP actually
functions — i.e. the LAN, not the tunnel.

WireGuard is only responsible for **routing** the packet as far as the home
node. Once it arrives, the home node **forwards** it onto the LAN, where
normal ARP resolves the rest.

---

## Components

### 1. MetalLB

Provides a real, routable IP to the `ingress-nginx` Service. Configured in
L2 (ARP) mode.

`IPAddressPool` — deliberately a single `/32` address, not a range. Every
address handed out is explicit and pre-checked against the existing LAN to
avoid colliding with real devices (K8s nodes, router, etc.):

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: wireguard-pool
  namespace: metallb-system
spec:
  addresses:
    - 10.0.0.70/32
    # add more ips for other protocols (maybe smtp for fun?)
```

`L2Advertisement` — tells MetalLB to announce addresses from that pool via
ARP on the LAN:

```yaml
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: wireguard-l2
  namespace: metallb-system
spec:
  ipAddressPools:
    - wireguard-pool
```

> Only **one** IP is provisioned because there is only ever one
> `LoadBalancer`-type Service in this cluster: `ingress-nginx`. Every HTTP
> app is routed through it by hostname — no new IP is needed per app.
> A new `/32` would only be needed for a future service that can't use
> HTTP hostname routing (e.g. raw TCP like SMTP), or via ingress-nginx's
> TCP/UDP passthrough instead.

### 2. ingress-nginx

Installed as a `LoadBalancer` Service, requesting the MetalLB IP above:

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress --create-namespace \
  --set controller.service.loadBalancerIP=10.0.0.70
```

Verify:
```bash
kubectl get svc -n ingress
# EXTERNAL-IP should show 10.0.0.70
```

### 3. Per-app Ingress resources

Every app gets a hostname-routed `Ingress` object pointing at the same
`10.0.0.70` — no new IP, no new WireGuard/nginx config beyond DNS + one
proxy block.

Example (Grafana):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grafana-ingress
  namespace: monitoring
spec:
  ingressClassName: nginx
  rules:
    - host: grafana.dnaserver.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: monitoring-grafana
                port:
                  number: 80
```

Local test (bypasses DNS, simulates the real Host header):
```bash
curl -I -H "Host: grafana.dnaserver.com" http://10.0.0.70
```

### 4. WireGuard (home node ↔ Linode) (Extra configuration needed to be done since ARP couldnt be sent over Wireguard protocol, I've made this update on wireguard-setup service as well)

The tunnel's own endpoint addresses (`10.8.0.2` home / `10.8.0.1` Linode)
only let the two peers talk to each other directly. `AllowedIPs` is what
lets **other** networks ride through the tunnel — it is not limited to the
tunnel's own subnet.

On **Linode**, `/etc/wireguard/wg0.conf`, the peer block for the home node:

```ini
[Peer]
PublicKey = <home-node-public-key>
AllowedIPs = 10.8.0.2/32, 10.0.0.70/32
Endpoint = <home-public-ip-or-ddns>:<port>
```

Only the specific ingress IP (`10.0.0.70/32`) is added 

Reload after editing:
```bash
sudo wg-quick down wg0
sudo wg-quick up wg0
sudo wg show   # confirm AllowedIPs updated, handshake is recent
```

### 5. IP forwarding on the home node

Required so the home node passes tunnel traffic through to the real LAN
instead of only accepting traffic addressed to itself.

```bash
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward = 1" | sudo tee -a /etc/sysctl.conf

sudo iptables -A FORWARD -i wg0 -o eth0 -j ACCEPT
sudo iptables -A FORWARD -i eno1 -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT
```


> These iptables rules are not persistent by default — add
> `iptables-persistent` (or equivalent) so they survive a reboot.

### 6. Linode nginx reverse proxy (TBD on dna-nginx-server)

Terminates the public hostname and forwards to the ingress IP over the
WireGuard tunnel.

`/etc/nginx/sites-available/grafana`:

```nginx
server {
    listen 80;
    server_name grafana.dnaserver.com;

    location / {
        proxy_pass http://10.0.0.70;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and reload:
```bash
sudo ln -s /etc/nginx/sites-available/grafana /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # avoid default site catching requests first
sudo nginx -t
sudo systemctl reload nginx
```

> TLS (Let's Encrypt via certbot, DNS-01 challenge against Cloudflare) is
> the next step to add here — currently only plain HTTP is configured.

### 7. Cloudflare DNS

`A` record: `grafana.dnaserver.com` → Linode's public IP.

---

## Adding a new app later (checklist)

For any new **HTTP-based** app:

1. `Ingress` resource in Kubernetes, same `ingressClassName: nginx`, new
   `host:` value → same `10.0.0.70`, no new MetalLB IP.
2. New `server {}` block in Linode nginx, new `server_name`, same
   `proxy_pass http://10.0.0.70;`.
3. New DNS `A`/`CNAME` record in Cloudflare.
4. New TLS cert for the new hostname (once TLS is set up).

No new WireGuard config, no new MetalLB pool entry, no new firewall rules.

For a **non-HTTP** service (e.g. SMTP, raw TCP) (TBD):
- Either give it its own dedicated MetalLB `/32` + WireGuard `AllowedIPs`
  entry, or
- Use ingress-nginx's TCP/UDP passthrough ConfigMap to route by port on the
  existing `10.0.0.70` IP instead.

---
