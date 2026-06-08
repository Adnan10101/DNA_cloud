# WireGuard Homelab — Quick Setup

Goal: a repeatable WireGuard setup for Internet → VPS → Home → Laptop using a single VPN subnet (recommended). An optional hub‑and‑spoke variant is included for segmented setups.

## Prerequisites
- `wireguard` installed on VPS, Home, Laptop
- root access on each device
- open UDP port `51820` on the VPS firewall

---

## Create interface
```bash
ip link add dev wg0 type wireguard
ip address add dev wg0 <ip-address>
ip link set up dev wg0
```

## Common: generate keys (on each device)
```bash
sudo mkdir -p /etc/wireguard
cd /etc/wireguard
umask 077
wg genkey | tee privatekey | wg pubkey > publickey
# keep `privatekey` private; share `publickey` with peers
wg set wg0 private-key /etc/wireguard/privatekey
```

Check status:
```bash
wg show
ip a show wg0
```

## Method A — Flat single-subnet (Recommended)
- VPN subnet: `10.8.0.0/24`
- Peers: VPS=10.8.0.1, Home=10.8.0.2, Laptop=10.8.0.3

### Example `wg0.conf` — VPS
```ini
[Interface]
Address = 10.8.0.1/24
ListenPort = 51820
PrivateKey = <VPS_PRIVATE_KEY>

# peer: Home
[Peer]
PublicKey = <HOME_PUBLIC_KEY>
AllowedIPs = 10.8.0.2/32

# peer: Laptop
[Peer]
PublicKey = <LAPTOP_PUBLIC_KEY>
AllowedIPs = 10.8.0.3/32
```

### Example `wg0.conf` — Home
```ini
[Interface]
Address = 10.8.0.2/24
PrivateKey = <HOME_PRIVATE_KEY>

[Peer]
PublicKey = <VPS_PUBLIC_KEY>
Endpoint = <VPS_PUBLIC_IP>:51820
AllowedIPs = 10.8.0.1/32
PersistentKeepalive = 25

[Peer]
PublicKey = <LAPTOP_PUBLIC_KEY>
AllowedIPs = 10.8.0.3/32
```

### Example `wg0.conf` — Laptop
```ini
[Interface]
Address = 10.8.0.3/24
PrivateKey = <LAPTOP_PRIVATE_KEY>

[Peer]
PublicKey = <VPS_PUBLIC_KEY>
Endpoint = <VPS_PUBLIC_IP>:51820
AllowedIPs = 10.8.0.0/24
PersistentKeepalive = 25
```

Notes:
- Laptop uses VPS as endpoint so it can join via the public entrypoint.
- Add Laptop peer to VPS and Home (public key + `AllowedIPs=10.8.0.3/32`) so both know the route.

### Add peer dynamically (wg set)
```bash
# on Home (add laptop)
wg set wg0 peer <LAPTOP_PUBLIC_KEY> allowed-ips 10.8.0.3/32

# on VPS (add laptop)
wg set wg0 peer <LAPTOP_PUBLIC_KEY> allowed-ips 10.8.0.3/32
```

### Enable IP forwarding on Home (services live here)
```bash
sudo sysctl -w net.ipv4.ip_forward=1
# to persist: set net.ipv4.ip_forward=1 in /etc/sysctl.conf or /etc/sysctl.d/*.conf
```

### Minimal firewall tips
- On VPS (allow WG, restrict forwarding to Home):
```bash
sudo iptables -A INPUT -p udp --dport 51820 -j ACCEPT
sudo iptables -A FORWARD -i wg0 -d 10.8.0.2 -j ACCEPT
sudo iptables -A FORWARD -j DROP
```
- On Home (permit WG and enforce internal policies):
```bash
sudo iptables -A INPUT -i wg0 -j ACCEPT
sudo iptables -A FORWARD -i wg0 -j ACCEPT
```

### Start & persist
```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

### Quick verification
```bash
# from Laptop
ping 10.8.0.1   # VPS
ping 10.8.0.2   # Home

# from Home
ping 10.8.0.3   # Laptop
```

---

## Method B — Hub-and-Spoke (Advanced)
Use only when you need segmentation (edge vs internal). More complex and easy to misconfigure.

- Example subnets:
  - VPS ↔ Home = `10.8.0.0/24` (VPS:10.8.0.1, Home:10.8.0.2)
  - Home ↔ Laptop = `10.9.0.0/24` (Home:10.9.0.1, Laptop:10.9.0.2)

Key points:
- Home must forward between subnets (enable `net.ipv4.ip_forward`).
- VPS must include `10.9.0.0/24` in Home's `AllowedIPs` so traffic is handed to Home.
- Optionally NAT laptop behind Home if you want Home to hide internal addresses:
```bash
# on Home (masquerade 10.9 going out to internet via eth0)
