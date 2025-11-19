# backend/routers/yaml_gen.py

from fastapi import APIRouter
from pydantic import BaseModel

from agentctl.agent import K8sAgent
from agentctl.config import settings

router = APIRouter(tags=["YAML Generation"])

agent = K8sAgent()


class GenerateYAMLRequest(BaseModel):
    prompt: str
    namespace: str | None = None
    kind: str | None = "Auto"


class GenerateYAMLResponse(BaseModel):
    yaml: str


@router.post("/generate-yaml", response_model=GenerateYAMLResponse)
def generate_yaml(req: GenerateYAMLRequest):
    """
    Natural language → Kubernetes YAML using your K8sAgent.
    """
    ns = req.namespace or settings.k8s_namespace
    kind_sel = None if (req.kind is None or req.kind == "Auto") else req.kind

    # your existing agent logic returns (explanation, yaml_text)
    _, yaml_text = agent.nl_to_resource_yaml(
        req.prompt,
        namespace=ns,
        kind=kind_sel,
    )

    return GenerateYAMLResponse(yaml=yaml_text)
