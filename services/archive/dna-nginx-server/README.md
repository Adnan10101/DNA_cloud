How to deploy the load balancer:

DO:
helm install load-balancer services/dna-nginx-server/dna-server 

This installs the load balancer into the cluster.

Haven't automated the index.html file. So do the following to update the "dnacloudserver.home:30800" or "main.dnacloudserver.home:30800"

exec into the load balancer pod

echo {contents-from-index.html} > /usr/share/nginx/html/index.html