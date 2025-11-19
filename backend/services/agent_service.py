from agentctl.agent import K8sAgent
from agentctl.config import settings


class AgentService:
    """
    Wrapper for the LLM → YAML agent.
    """

    def __init__(self):
        self.agent = K8sAgent()

    def generate_yaml(self, prompt: str, namespace: str | None, kind: str | None):
        # fallback to default namespace from config
        ns = namespace or settings.k8s_namespace
        kind_sel = None if (kind is None or kind == "Auto") else kind

        # returns: (explanation, yaml_text)
        _, yaml_text = self.agent.nl_to_resource_yaml(
            prompt,
            namespace=ns,
            kind=kind_sel,
        )

        return yaml_text


# Shared singleton
agent_service = AgentService()
