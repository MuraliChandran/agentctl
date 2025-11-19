"""Minimal Kubernetes HTTP client using the public API exposed via ngrok."""

from __future__ import annotations
import json
from typing import Dict, Any, List
import requests
import yaml

from .config import settings
from .schemas import ApplyResult, JobStatus, PodInfo, ClusterSnapshot

class K8sClient:
    def __init__(self, base_url: str | None = None, namespace: str | None = None):
        if not base_url:
            base_url = settings.k8s_api_base_url
        if not base_url:
            raise ValueError("K8S_API_BASE_URL is not set.")

        self.base_url = base_url.rstrip("/")
        self.namespace = namespace or settings.k8s_namespace
        self.verify_ssl = settings.verify_ssl
        self.bearer_token = settings.k8s_bearer_token

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.bearer_token:
            h["Authorization"] = f"Bearer {self.bearer_token}"
        return h

    def _request(self, method: str, path: str, json_body: Dict[str, Any] | None = None):
        url = f"{self.base_url}{path}"
        resp = requests.request(
            method=method,
            url=url,
            headers=self._headers(),
            json=json_body,
            verify=self.verify_ssl,
            timeout=30,
        )
        return resp

    def apply_manifest(self, manifest_yaml: str) -> ApplyResult:
        try:
            manifest = yaml.safe_load(manifest_yaml)
        except yaml.YAMLError as e:
            return ApplyResult(success=False, message=f"Invalid YAML: {e}")


        kind = manifest.get("kind")
        meta = manifest.get("metadata", {})
        name = meta.get("name")
        ns = meta.get("namespace", self.namespace)

        if kind == "Job":
            path = f"/apis/batch/v1/namespaces/{ns}/jobs"
        elif kind == "Deployment":
            path = f"/apis/apps/v1/namespaces/{ns}/deployments"
        else:
            return ApplyResult(success=False, message=f"Unsupported kind: {kind}")

        resp = self._request("POST", path, manifest)

        try:
            raw = resp.json()
        except:
            raw = {"raw": resp.text}

        if resp.status_code in (200, 201):
            return ApplyResult(
                success=True,
                message=f"Created {kind} '{name}'",
                raw_response=raw,
            )


        return ApplyResult(success=False,
            message=f"K8s API error {resp.status_code}: {raw}",
            raw_response=raw,
            )


    def list_jobs(self):
        path = f"/apis/batch/v1/namespaces/{self.namespace}/jobs"
        resp = self._request("GET", path)
        items = resp.json().get("items", [])
        out = []
        for it in items:
            meta = it.get("metadata", {})
            st = it.get("status", {})
            out.append(JobStatus(
                name=meta.get("name"),
                namespace=meta.get("namespace", self.namespace),
                succeeded=st.get("succeeded", 0),
                failed=st.get("failed", 0),
                active=st.get("active", 0)
            ))
        return out

    def list_pods(self):
        resp = self._request("GET", f"/api/v1/namespaces/{self.namespace}/pods")
        items = resp.json().get("items", [])
        out = []
        for it in items:
            meta = it.get("metadata", {})
            st = it.get("status", {})
            out.append(PodInfo(
                name=meta.get("name"),
                phase=st.get("phase", "Unknown"),
                node_name=st.get("nodeName")
            ))
        return out

    def get_pod_logs(self, pod: str, tail_lines: int = 100):
        resp = requests.get(
            f"{self.base_url}/api/v1/namespaces/{self.namespace}/pods/{pod}/log",
            params={"tailLines": tail_lines},
            headers=self._headers(),
            verify=self.verify_ssl,
            timeout=30
        )
        if resp.status_code == 200:
            return resp.text
        return f"Error {resp.status_code}: {resp.text}"

    def snapshot(self):
        return ClusterSnapshot(
            namespace=self.namespace,
            jobs=self.list_jobs(),
            pods=self.list_pods()
        )
