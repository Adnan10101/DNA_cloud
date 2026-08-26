# TLS Setup for dna-server.com Homelab

This README documents how HTTPS/TLS is configured for the homelab, how to add
new subdomains/services, and how to sanity-check that traffic is actually
encrypted using Wireshark.

## Architecture (claude can come up with wacko diagrams huh)

```
Client (browser) --HTTPS (443)--> Linode (public IP, nginx, TLS termination)
                                        |
                                        | WireGuard tunnel (encrypted at network layer)
                                        v
                                  Home server (10.0.0.70) --HTTP--> backend app
```

- TLS is terminated on the **Linode box**, since it's the only machine with a
  public IP that Let's Encrypt can validate against. Also traffic from Linode to the home server travels over the WireGuard tunnel,
  which is already encrypted at the network layer, so plain HTTP on that
  internal leg is fine there.
- Certificates issued on Linode via **Certbot**.

## Initial TLS Setup (Steps taken to add TLS)

1. Point your domain's DNS A record (in Cloudflare) at the Linode public IP.


2. Need to stop nginx (standalone needs port 80 free):
   ```bash
   sudo systemctl stop nginx
   ```

3. Request the certificate, listing every domain/subdomain it should cover:
   ```bash
   sudo certbot certonly --standalone -d dna-server.com -d files.dna-server.com -d <add-all-subdomains-here>
   ```

4. Start nginx back up:
   ```bash
   sudo systemctl start nginx
   ```

5. Confirm the cert and its covered domains:
   ```bash
   sudo certbot certificates
   ```

## UPDATE nginx Server Block Template 


```nginx
server {
    listen 443 ssl;
    server_name files.dna-server.com;

    ssl_certificate     <path-to-fullchain.pem>;
    ssl_certificate_key <path-to-privkey.pem>;

    location / {
        proxy_pass http://10.0.0.70;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Adding a New Subdomain

Two options:

### Option A: Add the subdomain to the existing multi-domain cert (like the above method *annoying*)

1. Add a DNS A record for the new subdomain in Cloudflare (grey cloud, points
   to the Linode IP).
2. Reissue the cert including the new domain:
   ```bash
   sudo systemctl stop nginx
   sudo certbot certonly --standalone \
     -d dna-server.com \
     -d files.dna-server.com \
     -d newsubdomain.dna-server.com
   sudo systemctl start nginx
   ```
3. Add a new `server { }` block in nginx for the new subdomain (same template
   as above, just change `server_name` and `proxy_pass` target).
4. Test config and reload:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### Option B — Switch to a wildcard cert (havent tried it yet but noting it down)

A wildcard cert (`*.dna-server.com`) covers all current and future
subdomains without reissuing every time. Requires DNS-01 validation via
Cloudflare instead of HTTP-01 (need to learn this difference):

```bash
sudo certbot certonly --manual --preferred-challenges dns \
  -d "dna-server.com" -d "*.dna-server.com"
```

Certbot will give a TXT record value to add in Cloudflare DNS; add it,
then confirm in the certbot prompt. Once issued, every
new `server { }` block just references the same wildcard cert — no more
reissuing needed. (Automating this with `certbot-dns-cloudflare` avoids the
manual TXT step on renewal.)


## Wireshark Sanity Check (Verifying Encryption)

This confirms that credentials and URLs are actually encrypted on the wire,
not just "trusted" by the browser.

1. Filter to only your server's traffic:
   ```
   ip.addr == <linode public IP>
   ```
2. Submit a test login in the browser.
3. Stop the capture and inspect packets:
   - Packets will show as `TLSv1.3 Application Data` — this is encrypted
     ciphertext, not readable text.
   - The only plaintext visible is the **SNI hostname** in the initial
     `Client Hello` packet (filter: `tls.handshake.extensions_server_name`)
     — this reveals the domain (e.g. `files.dna-server.com`) but not the
     path, query string, or form payload.
4. **What you should NOT see:** the literal path (`/login?user=...`), form
   fields, or password anywhere in plaintext. If you do, TLS is not actually
   working correctly. (kinda obvious given the fact that wireshark will display the protocol used (TLS or HTTP))


## Renewal stuff

Certbot sets up an automatic renewal timer by default. Verify it's active:

```bash
sudo systemctl status certbot.timer
```

Test a dry-run renewal without actually reissuing:

```bash
sudo certbot renew --dry-run
```