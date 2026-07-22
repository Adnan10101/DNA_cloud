# nginx config — adding a new app

This nginx instance (on Linode) is the public entry point. It proxies each
hostname over the WireGuard tunnel to home cluster's ingress-nginx ip. Adding a new app does **not** require touching WireGuard,
MetalLB, or firewall rules — just the steps below. (reminder to my future self)

## Steps to expose a new app

1. **Create the Ingress in Kubernetes** (home cluster), pointing at the new
   app's Service, with the hostname you want:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: myapp-ingress
     namespace: myapp
   spec:
     ingressClassName: nginx
     rules:
       - host: myapp.dna-server.com
         http:
           paths:
             - path: /
               pathType: Prefix
               backend:
                 service:
                   name: myapp-service
                   port:
                     number: 8080
   ```
   Test locally first (from LAN or after tunnel test):
   ```bash
   curl -I -H "Host: myapp.dnaserver.com" http://10.0.0.70
   ```

2. **Add a server block to `nginx.conf`** (this folder), same pattern as
   existing ones — just change `server_name` and (if you want TLS) the cert
   paths:
   ```nginx
   server {
       listen 80;
       server_name myapp.dnaserver.com;

       location / {
           proxy_pass http://10.0.0.70;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
   `proxy_pass` is always `http://10.0.0.70` — this never changes, regardless
   of the app. Routing to the right backend happens inside the cluster via
   the `Host` header, not here.

3. **Test and reload nginx**:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

4. **Add the DNS record** in Cloudflare: `A` record, `myapp.dnaserver.com` →
   Linode's public IP.

5. **Test end to end**:
   ```bash
   curl -I http://myapp.dnaserver.com
   ```

## Notes

- Never leave `sites-enabled/default` (or `default-backup`) linked — it can
  catch requests before your real server blocks match. Keep it removed.
- Every new app reuses the same `10.0.0.70` — no new IP, no new MetalLB
  entry, no new WireGuard config. Only needed for non-HTTP services (raw
  TCP, etc.) — different process, not covered here.
