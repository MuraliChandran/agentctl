from agentctl.k8s_client import K8sClient


class K8sService:
    """
    Simple wrapper around your existing K8sClient.
    This allows FastAPI routes to call Kubernetes operations
    without importing K8sClient directly in every router.
    """

    def __init__(self):
        self.client = K8sClient()

    # ---- Apply YAML ----
    def apply_manifest(self, yaml_text: str):
        return self.client.apply_manifest(yaml_text)

    # ---- Snapshot ----
    def snapshot(self):
        return self.client.snapshot()

    # ---- Logs ----
    def get_pod_logs(self, pod_name: str, tail_lines: int = 100):
        return self.client.get_pod_logs(pod_name, tail_lines=tail_lines)


# Shared singleton instance
k8s_service = K8sService()
