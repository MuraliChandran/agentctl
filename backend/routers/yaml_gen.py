from fastapi import APIRouter
from pydantic import BaseModel
from agentctl.agent import K8sAgent
from agentctl.config import settings

router = APIRouter(prefix="/api", tags=["YAML Generation"])

agent = K8sAgent()

class GenerateRequest(BaseModel):
    prompt: str
    namespace: str | None = None
    kind: str | None = "Auto"

class GenerateResponse(BaseModel):
    yaml: str

@router.post("/generate-yaml", response_model=GenerateResponse)
def generate_yaml(req: GenerateRequest):
    ns = req.namespace or settings.k8s_namespace
    kind = None if req.kind == "Auto" else req.kind
    _, yaml_text = agent.nl_to_resource_yaml(req.prompt, ns, kind)
    return GenerateResponse(yaml=yaml_text)
