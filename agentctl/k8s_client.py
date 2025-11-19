"""Minimal Kubernetes HTTP client using the public API exposed via ngrok."""

from __future__ import annotations

import json
from typing import Dict, Any, List

import requests
import yaml

from .config import settings
from .schemas import (
    ApplyResult,
    JobStatus,
    PodInfo,
    ClusterSnapshot,
    DeploymentStatus,
    CronJobStatus,
)


class K8sClient:
    def __init__(self, base_url: str | None = None, namespace: str | None = None):
        if not base_url:
            base_url = settings.k8s_api_base_url
        if not base_url:
            raise ValueError("K8S_API_BASE_URL is not set. Configure it in env.")

        self.base_url = base_url.rstrip("/")
        self.namespace = namespace or settings.k8s_namespace
        self.verify_ssl = settings.verify_ssl
        self.bearer_token = settings.k8s_bearer_token

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        json_body: Dict[str, Any] | None = None,
    ) -> requests.Response:
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

    # ------------------------------------------------------------------ #
    # Apply a manifest (Job / Deployment / CronJob)                      #
    # ------------------------------------------------------------------ #

    def apply_manifest(self, manifest_yaml: str) -> ApplyResult:
        """Create a resource (Job / Deployment / CronJob) from YAML."""
        try:
            manifest = yaml.safe_load(manifest_yaml)
        except yaml.YAMLError as e:
            return ApplyResult(success=False, message=f"Invalid YAML: {e}")

        if not isinstance(manifest, dict):
            return ApplyResult(success=False, message="Manifest must be a single YAML object.")

        kind = manifest.get("kind")
        metadata = manifest.get("metadata", {})
        name = metadata.get("name", "<unnamed>")
        namespace = metadata.get("namespace", self.namespace)

        if kind == "Job":
            path = f"/apis/batch/v1/namespaces/{namespace}/jobs"
        elif kind == "Deployment":
            path = f"/apis/apps/v1/namespaces/{namespace}/deployments"
        elif kind == "CronJob":
            path = f"/apis/batch/v1/namespaces/{namespace}/cronjobs"
        else:
            return ApplyResult(success=False, message=f"Unsupported kind: {kind}")

        resp = self._request("POST", path, json_body=manifest)

        try:
            raw = resp.json()
        except json.JSONDecodeError:
            raw = {"raw_text": resp.text}

        if resp.status_code in (200, 201):
            return ApplyResult(
                success=True,
                message=f"Created {kind} '{name}' in ns '{namespace}'.",
                raw_response=raw,
            )

        return ApplyResult(
            success=False,
            message=f"K8s API error {resp.status_code}: {raw}",
            raw_response=raw,
        )

    # ------------------------------------------------------------------ #
    # List helpers for dashboard                                         #
    # ------------------------------------------------------------------ #

    def list_jobs(self) -> List[JobStatus]:
        path = f"/apis/batch/v1/namespaces/{self.namespace}/jobs"
        resp = self._request("GET", path)
        data = resp.json()
        items = data.get("items", [])
        jobs: List[JobStatus] = []
        for item in items:
            meta = item.get("metadata", {})
            status = item.get("status", {})
            jobs.append(
                JobStatus(
                    name=meta.get("name", "<unknown>"),
                    namespace=meta.get("namespace", self.namespace),
                    succeeded=status.get("succeeded", 0) or 0,
                    failed=status.get("failed", 0) or 0,
                    active=status.get("active", 0) or 0,
                )
            )
        return jobs

    def list_pods(self) -> List[PodInfo]:
        path = f"/api/v1/namespaces/{self.namespace}/pods"
        resp = self._request("GET", path)
        data = resp.json()
        items = data.get("items", [])
        pods: List[PodInfo] = []
        for item in items:
            meta = item.get("metadata", {})
            status = item.get("status", {})
            pods.append(
                PodInfo(
                    name=meta.get("name", "<unknown>"),
                    phase=status.get("phase", "Unknown"),
                    node_name=status.get("nodeName"),
                )
            )
        return pods

    def list_deployments(self) -> List[DeploymentStatus]:
        path = f"/apis/apps/v1/namespaces/{self.namespace}/deployments"
        resp = self._request("GET", path)
        data = resp.json()
        items = data.get("items", [])
        out: List[DeploymentStatus] = []
        for item in items:
            meta = item.get("metadata", {})
            st = item.get("status", {})
            out.append(
                DeploymentStatus(
                    name=meta.get("name", "<unknown>"),
                    namespace=meta.get("namespace", self.namespace),
                    replicas=st.get("replicas", 0) or 0,
                    ready=st.get("readyReplicas", 0) or 0,
                )
            )
        return out

    def list_cronjobs(self) -> List[CronJobStatus]:
        path = f"/apis/batch/v1/namespaces/{self.namespace}/cronjobs"
        resp = self._request("GET", path)
        data = resp.json()
        items = data.get("items", [])
        out: List[CronJobStatus] = []
        for item in items:
            meta = item.get("metadata", {})
            st = item.get("status", {})
            last = st.get("lastScheduleTime")
            out.append(
                CronJobStatus(
                    name=meta.get("name", "<unknown>"),
                    namespace=meta.get("namespace", self.namespace),
                    active=len(st.get("active", []) or []),
                    last_schedule=str(last) if last is not None else None,
                )
            )
        return out

    def get_pod_logs(self, pod_name: str, container: str | None = None, tail_lines: int = 100) -> str:
        params = {"tailLines": str(tail_lines)}
        if container:
            params["container"] = container

        path = f"/api/v1/namespaces/{self.namespace}/pods/{pod_name}/log"
        url = f"{self.base_url}{path}"
        resp = requests.get(url, headers=self._headers(), params=params, verify=self.verify_ssl, timeout=30)
        if resp.status_code == 200:
            return resp.text
        return f"Error {resp.status_code}: {resp.text}"

    def snapshot(self) -> ClusterSnapshot:
        return ClusterSnapshot(
            namespace=self.namespace,
            jobs=self.list_jobs(),
            pods=self.list_pods(),
            deployments=self.list_deployments(),
            cronjobs=self.list_cronjobs(),
        )
