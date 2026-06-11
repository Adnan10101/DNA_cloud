# WireGuard Homelab — Quick Setup

Goal: a repeatable WireGuard setup for Internet → VPS → Home → Laptop using a single VPN subnet (recommended). An optional hub‑and‑spoke variant is included for segmented setups.

## Prerequisites
- `wireguard` installed on VPS, Home, Laptop
- root access on each device
- open UDP port `51820` on the VPS firewall

---

# Common: generate keys (on each device) (MUST)
```bash
sudo mkdir -p /etc/wireguard
cd /etc/wireguard
umask 077
wg genkey | tee privatekey | wg pubkey > publickey
# keep `privatekey` private; share `publickey` with peers
wg set wg0 private-key /etc/wireguard/privatekey
```

# Method 1 (Linux commands not persistent)

## Create interface
```bash
ip link add dev wg0 type wireguard
ip address add dev wg0 <ip-address>
wg set wg0 private-key ./privatekey
ip link set up dev wg0
```

Check status:
```bash
wg show
ip a show wg0
```

## Set Peers
```bash 
wg set wg0 peer <public-key-of-peer> allowed-ips <wireguard ip-of-peer-or-subnet> endpoint <main-interface-ip-of-peer>:<wireguard-port-of-peer>
```

Example:

- VPN subnet: `192.168.0.0/24`
- Peers: 
    1. VPS=192.168.0.1, PUBLIC_KEY = ABCDE, ENS0 = 10.0.0.128, WIREGUARD-PORT = 39009
    2. Home=192.168.0.2, PUBLIC_KEY = XYZ, ENS0 = 10.0.0.40, WIREGUARD-PORT = 38990

```bash
Peering Home with VPS
wg set wg0 peer XYZ allowed-ips 192.168.0.2/32 endpoint 10.0.0.40:38990

Peering VPS with Home
wg set wg0 peer ABCDE allowed-ips 192.168.0.1/32 endpoint 10.0.0.128:39009
```

## Test
```bash
ping 192.168.0.1 or ping 192.168.0.2
```
# Method 2 (Persistent, wg-quick)
Create a wg0.conf file in /etc/wireguard/

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

## Bring it up
```bash
sudo wg-quick up wg0
```

Notes (Optional):
- Laptop uses VPS as endpoint so it can join via the public entrypoint.
- Add Laptop peer to VPS and Home (public key + `AllowedIPs=10.8.0.3/32`) so both know the route.


### Quick verification
```bash
# from Laptop
ping 10.8.0.1   # VPS
ping 10.8.0.2   # Home

# from Home
ping 10.8.0.3   # Laptop
```
### After Wireguard setup
Once ping from device to VPS and VPS to server works, enable ip_forward = 1
and then add

```bash
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT
```
To VPS [Interface]