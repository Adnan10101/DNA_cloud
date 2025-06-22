## MinIO Tenants on Kubernetes

Provisions S3-compatible MinIO tenants using the MinIO Operator in a Kubernetes cluster. Each tenant runs an isolated MinIO server with its own storage, console UI, and access credentials. 

### Deploy a Tenant
Before deploying a Tenant a PV and new namespace (from the minio tenant docs) should be created.

1. Create a PV:

    oc create -f claims/pv1.yaml

2. Create ns

   oc create namespace <namespace>
   
3. Edit and apply tenant-values.yaml:

    helm install <relase-name> tenant -n <namespace> -f claims/example_tenant.yaml

### Accessing MinIO
Console UI (port-forward):

kubectl port-forward svc/tenant1-console -n test-tenant 9090:9090
