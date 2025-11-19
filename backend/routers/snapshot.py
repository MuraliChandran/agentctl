# backend/routers/snapshot.py

from fastapi import APIRouter

from agentctl.k8s_client import K8sClient

router = APIRouter(tags=["Cluster Snapshot"])


@router.get("/snapshot")
def get_snapshot():
    """
    Return a JSON snapshot of Jobs, Pods, Deployments, CronJobs in the namespace.
    """
    client = K8sClient()
    snap = client.snapshot()

    def job_to_dict(j):
        return {
            "name": getattr(j, "name", None),
            "succeeded": getattr(j, "succeeded", None),
            "failed": getattr(j, "failed", None),
            "active": getattr(j, "active", None),
        }

    def pod_to_dict(p):
        return {
            "name": getattr(p, "name", None),
            "phase": getattr(p, "phase", None),
        }

    def deploy_to_dict(d):
        return {
            "name": getattr(d, "name", None),
            "replicas": getattr(d, "replicas", None),
            "ready": getattr(d, "ready", None),
        }

    def cron_to_dict(c):
        return {
            "name": getattr(c, "name", None),
            "active": getattr(c, "active", None),
            # your schema likely calls this last_schedule or lastScheduleTime
            "last_schedule": getattr(c, "last_schedule", None)
            or getattr(c, "lastScheduleTime", None),
        }

    return {
        "namespace": getattr(snap, "namespace", None),
        "jobs": [job_to_dict(j) for j in snap.jobs],
        "pods": [pod_to_dict(p) for p in snap.pods],
        "deployments": [deploy_to_dict(d) for d in snap.deployments],
        "cronjobs": [cron_to_dict(c) for c in snap.cronjobs],
    }
