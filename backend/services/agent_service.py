import uuid
import yaml

from agentctl.agent import K8sAgent
from agentctl.config import settings
from agentctl.llm import ask_llm


def randomize_name(yaml_text: str) -> str:
    try:
        obj = yaml.safe_load(yaml_text)
        if not isinstance(obj, dict):
            return yaml_text

        kind = obj.get("kind")
        if kind not in ("Job", "Deployment", "CronJob"):
            return yaml_text

        metadata = obj.setdefault("metadata", {})
        name = metadata.get("name")
        if not name:
            return yaml_text

        suffix = str(uuid.uuid4())[:5]
        metadata["name"] = f"{name}-{suffix}"

        return yaml.dump(obj, sort_keys=False)

    except Exception:
        return yaml_text

class AgentService:
    """
    Upgraded AgentService:
    - Primary: LLM generates plan → YAML
    - Fallback: Use existing K8sAgent.nl_to_resource_yaml
    """
    def __init__(self):
        # Your existing rule-based agent
        self.agent = K8sAgent()

    async def generate_yaml(self, prompt: str, namespace: str | None, kind: str | None):
        # default namespace
        ns = namespace or settings.k8s_namespace
        kind_sel = None if (kind is None or kind == "Auto") else kind

        # -------------------------------
        # 1) LLM Planning Step
        # -------------------------------
        plan_prompt = f"""
        You are an expert Kubernetes engineer.

        Convert this natural-language instruction into a detailed,
        step-by-step Kubernetes workload plan (NO YAML yet).

        Instruction:
        {prompt}

        Include:
        - workload type (Job / Deployment / CronJob)
        - container image
        - commands/args
        - resources
        - environment variables
        - namespace: {ns}
        - override kind (if the user forced one): {kind_sel or "Auto"}
        """

        try:
            plan = await ask_llm(plan_prompt)
        except Exception as e:
            print(f"[LLM ERROR: plan] Falling back. Error: {e}")
            # fallback immediately
            _, yaml_text = self.agent.nl_to_resource_yaml(
                prompt,
                namespace=ns,
                kind=kind_sel,
            )
            return yaml_text

        # -------------------------------
        # 2) LLM YAML Generation Step
        # -------------------------------
        yaml_prompt = f"""
        Convert the following Kubernetes plan into VALID Kubernetes YAML.
        Output only the YAML (no explanation, no markdown).

        Plan:
        {plan}
        """

        try:
            yaml_text = await ask_llm(yaml_prompt)

            # sanity: avoid hallucinated empty responses
            if not yaml_text or len(yaml_text.strip()) == 0:
                raise ValueError("Empty YAML from LLM")

            return randomize_name(yaml_text)

        except Exception as e:
            print(f"[LLM ERROR: yaml] Falling back. Error: {e}")

            # -------------------------------
            # 3) Fallback to your legacy NLP → YAML
            # -------------------------------
            _, yaml_text = self.agent.nl_to_resource_yaml(
                prompt,
                namespace=ns,
                kind=kind_sel,
            )
            return randomize_name(yaml_text)

# Shared singleton
agent_service = AgentService()
