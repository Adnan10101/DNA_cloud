Create a secret similar to the following:

```yaml
apiVersion: v1
kind: Secret
metadata:
    name: ip-secret
stringData:
    public-ip: <public-ip>
    hub-ip: <private-ip>
```

configure the configmap to add/remove hostname
