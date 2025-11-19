from fastapi import APIRouter
from agentctl.k8s_client import K8sClient

router = APIRouter(prefix="/api", tags=["Logs"])

client = K8sClient()

@router.get("/logs")
def get_logs(pod_name: str, tail: int = 100):
    logs = client.get_pod_logs(pod_name, tail)
    return {"pod": pod_name, "tail": tail, "logs": logs}
