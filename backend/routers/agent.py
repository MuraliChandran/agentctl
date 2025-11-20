# routers/agent.py

from fastapi import APIRouter, HTTPException
from backend.services.agent_service import agent_service
from agentctl.k8s_client import K8sClient

router = APIRouter()


@router.post("/agent")
async def run_agent(payload: dict):
    """
    Agentic flow:
      1. LLM → Plan → YAML (fallback: K8sAgent)
      2. Apply YAML to Kubernetes
      3. Return yaml, mode, model, result
    """

    instruction = payload.get("instruction")
    namespace  = payload.get("namespace")
    kind       = payload.get("kind")

    if not instruction:
        raise HTTPException(status_code=400, detail="Missing instruction")

    # 1. Generate YAML (LLM + fallback) → returns dict
    agent_output = await agent_service.generate_yaml(
        instruction,
        namespace,
        kind
    )

    yaml_text = agent_output["yaml"]
    mode = agent_output["mode"]
    model = agent_output["model"]

    # 2. Apply YAML to K8s
    client = K8sClient()
    try:
        apply_result = client.apply_manifest(yaml_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"K8s apply failed: {e}")

    # 3. Return everything to UI
    return {
        "instruction": instruction,
        "yaml": yaml_text,
        "mode": mode,
        "model": model,
        "result": apply_result
    }
