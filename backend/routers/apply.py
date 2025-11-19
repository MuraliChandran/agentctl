# backend/routers/apply.py

from fastapi import APIRouter
from pydantic import BaseModel
import uuid
import yaml

from agentctl.k8s_client import K8sClient

router = APIRouter(tags=["Apply Manifest"])


class ApplyRequest(BaseModel):
    yaml: str


class ApplyResponse(BaseModel):
    success: bool
    message: str
    raw: str | None = None


def _inject_unique_name(yaml_text: str) -> str:
    """
    Add a short UUID suffix to metadata.name for Job/CronJob/Deployment
    to avoid 409 AlreadyExists errors when users re-apply the same YAML.
    """
    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return yaml_text

        kind = data.get("kind")
        if kind not in {"Job", "CronJob", "Deployment"}:
            return yaml_text

        meta = data.get("metadata") or {}
        base_name = meta.get("name")
        if not base_name:
            return yaml_text

        suffix = str(uuid.uuid4())[:5]
        new_name = f"{base_name}-{suffix}"
        meta["name"] = new_name
        data["metadata"] = meta

        # For CronJob make sure template labels are consistent
        if kind == "CronJob":
            tmpl = (
                data.get("spec", {})
                .get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
            )
            if isinstance(tmpl, dict):
                md = tmpl.get("metadata") or {}
                labels = md.get("labels") or {}
                labels["app"] = new_name
                md["labels"] = labels
                tmpl["metadata"] = md

        return yaml.safe_dump(data)
    except Exception:
        # on failure, just return original yaml
        return yaml_text


@router.post("/apply", response_model=ApplyResponse)
def apply_manifest(req: ApplyRequest):
    """
    Apply a YAML manifest to the Kubernetes cluster via K8sClient.
    """
    # Lazy K8sClient instantiation so missing env vars don't crash import
    client = K8sClient()

    final_yaml = _inject_unique_name(req.yaml)
    result = client.apply_manifest(final_yaml)

    try:
        raw_str = str(result.raw_response)
    except Exception:
        raw_str = None

    return ApplyResponse(
        success=result.success,
        message=result.message,
        raw=raw_str,
    )
