import os
from dataclasses import dataclass

@dataclass
class Settings:
    k8s_api_base_url: str = os.getenv("K8S_API_BASE_URL", "")
    k8s_namespace: str = os.getenv("K8S_NAMESPACE", "default")
    verify_ssl: bool = os.getenv("K8S_VERIFY_SSL", "false").lower() == "true"
    k8s_bearer_token: str | None = os.getenv("K8S_BEARER_TOKEN") or None

settings = Settings()
