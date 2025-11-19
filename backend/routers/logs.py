# backend/routers/logs.py

from fastapi import APIRouter, Query

from agentctl.k8s_client import K8sClient

router = APIRouter(tags=["Logs"])


@router.get("/logs")
def get_logs(
    pod_name: str = Query(..., description="Pod name from snapshot"),
    tail: int = Query(100, ge=1, le=1000, description="Tail lines"),
):
    """
    Return raw logs for a given pod (no HTML, just plain text).
    """
    client = K8sClient()
    text = client.get_pod_logs(pod_name.strip(), tail_lines=tail)
    return {"pod_name": pod_name, "tail": tail, "logs": text}
