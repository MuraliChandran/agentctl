from fastapi import APIRouter
from pydantic import BaseModel
import uuid, yaml

from agentctl.k8s_client import K8sClient

router = APIRouter(prefix="/api", tags=["Apply"])

client = K8sClient()

class ApplyRequest(BaseModel):
    yaml: str

class ApplyResponse(BaseModel):
    success: bool
    message: str
    raw: str

def inject_unique(yaml_text: str) -> str:
    try:
        obj = yaml.safe_load(yaml_text)
        kind = obj.get("kind")

        if kind in ["Job", "CronJob", "Deployment"]:
            suffix = str(uuid.uuid4())[:5]
            obj["metadata"]["name"] += f"-{suffix}"

        return yaml.safe_dump(obj)
    except:
        return yaml_text

@router.post("/apply", response_model=ApplyResponse)
def apply_resource(req: ApplyRequest):
    final_yaml = inject_unique(req.yaml)
    result = client.apply_manifest(final_yaml)
    raw = str(result.raw_response)
    return ApplyResponse(success=result.success, message=result.message, raw=raw)
