from fastapi import APIRouter
from agentctl.k8s_client import K8sClient

router = APIRouter(prefix="/api", tags=["Snapshot"])

client = K8sClient()

@router.get("/snapshot")
def snapshot():
    snap = client.snapshot()

    data = {
        "namespace": snap.namespace,
        "jobs": [vars(j) for j in snap.jobs],
        "pods": [vars(p) for p in snap.pods],
        "deployments": [vars(d) for d in snap.deployments],
        "cronjobs": [vars(c) for c in snap.cronjobs],
    }
    return data
