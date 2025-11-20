import uuid
import yaml

from agentctl.agent import K8sAgent
from agentctl.config import settings
from agentctl.llm import ask_llm, HF_MODEL  # <--- import model name


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
    def __init__(self):
        self.agent = K8sAgent()

    async def generate_yaml(self, prompt: str, namespace: str | None, kind: str | None):
        ns = namespace or settings.k8s_namespace
        kind_sel = None if (kind is None or kind == "Auto") else kind

        # -------------------------------
        # 1) LLM PLAN STEP
        # -------------------------------
        plan_prompt = f"""
        You are an expert Kubernetes engineer.
        Convert this natural-language instruction into a step-by-step plan.
        Instruction: {prompt}
        """

        try:
            plan = await ask_llm(plan_prompt)

        except Exception as e:
            print(f"[LLM ERROR: plan] Fallback. Error: {e}")

            _, yaml_text = self.agent.nl_to_resource_yaml(
                prompt, namespace=ns, kind=kind_sel
            )

            return {
                "yaml": randomize_name(yaml_text),
                "mode": "fallback",
                "model": None
            }

        # -------------------------------
        # 2) LLM YAML STEP
        # -------------------------------
        yaml_prompt = f"""
        Convert this Kubernetes plan into valid Kubernetes YAML.
        Output ONLY YAML:

        {plan}
        """

        try:
            yaml_text = await ask_llm(yaml_prompt)

            if not yaml_text or yaml_text.strip() == "":
                raise ValueError("Empty YAML from LLM")

            return {
                "yaml": randomize_name(yaml_text),
                "mode": "llm",
                "model": HF_MODEL
            }

        except Exception as e:
            print(f"[LLM ERROR: yaml] Fallback. Error: {e}")

            _, yaml_text = self.agent.nl_to_resource_yaml(
                prompt, namespace=ns, kind=kind_sel
            )

            return {
                "yaml": randomize_name(yaml_text),
                "mode": "fallback",
                "model": None
            }


agent_service = AgentService()
