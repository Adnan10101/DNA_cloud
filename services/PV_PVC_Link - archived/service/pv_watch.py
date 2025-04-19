from kubernetes import client, config, watch
import git_service
from jinja2 import Template

pvc_template = """
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
    name: {{ name }}
    namespace: {{ namespace }}
spec:
    accessModes:
    - {{ access_modes[0] if access_modes else 'ReadWriteOnce' }} # Ensure access modes are formatted as a list
    resources:
    requests:
        storage: {{ storage }}
    storageClassName: {{ storage_class_name if storage_class_name else 'None' }} # Default to standard if not provided
    volumeMode: {{ volume_mode  if volume_mode else 'Filesystem'  }} # Default to Filesystem if not provided
"""

def get_pvc_template(name, namespace, spec):
    template = Template(pvc_template)
    access_modes = spec.access_modes if spec.access_modes else []
    storage = spec.resources.requests["storage"]
    storage_class_name = getattr(spec, "storage_class_name", None)
    volume_mode = getattr(spec, "volume_mode", None)
    
    context = {
        "name": name,
        "namespace": namespace,
        "access_modes": access_modes,
        "storage": storage,
        "storage_class_name": storage_class_name,
        "volume_mode": volume_mode,
    }
    rendered_yaml = template.render(context)
    file_name = f"{name}_{namespace}.yaml"
    return file_name, rendered_yaml

def pv_watch():
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    w = watch.Watch()
    existing_pvcs = get_all_existing_pvcs()
    for event in w.stream(v1.list_persistent_volume_claim_for_all_namespaces):
        pvc =  event["object"]
        event_type = event["type"]
        if  event_type == "ADDED":
            namespace = pvc.metadata.namespace
            name = pvc.metadata.name
            if (namespace, name) in existing_pvcs:
                continue
            file_name, pvc_template = get_pvc_template(pvc.metadata.name, pvc.metadata.namespace, pvc.spec)
            git_service.push_pv_to_git(pvc_template, file_name)
            existing_pvcs.add((namespace, name))
            print("PVC Name: ",name,"PVC Namespace: ", namespace)
        if event_type == "DELETED":
            # TODO: when pvc gets deleted then remove it from the name and namespace 
            pass

def get_all_existing_pvcs():
    """
    Fetch all existing PVCs in the cluster and store them in a set.
    """
    v1 = client.CoreV1Api()
    existing_pvcs = set()
    pvcs = v1.list_persistent_volume_claim_for_all_namespaces().items
    for pvc in pvcs:
        existing_pvcs.add((pvc.metadata.namespace, pvc.metadata.name))
    return existing_pvcs