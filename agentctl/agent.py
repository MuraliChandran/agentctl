"""Natural language → Kubernetes Job YAML generator."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class JobSpecRequest:
    prompt: str
    name: str = "agentctl-job"
    image: str = "busybox:1.36"
    command: Optional[str] = "echo Hello && sleep 5"
    cpu: str = "500m"
    memory: str = "512Mi"
    namespace: str = "default"

class K8sAgent:

    def nl_to_job_request(self, text: str, namespace="default"):
        t = text.lower()
        name = "agentctl-job"

        if "preprocess" in t:
            name = "preprocess-job"
        elif "inference" in t:
            name = "inference-job"
        elif "train" in t:
            name = "training-job"

        image = "busybox:1.36"
        if "python" in t:
            image = "python:3.11-slim"
        if "pytorch" in t:
            image = "pytorch/pytorch:2.3.0-cuda12.1-cudnn9-runtime"

        command = "echo Hello && sleep 5"
        if "run python" in t:
            idx = t.find("run python")
            command = text[idx:].replace("run ", "").strip()

        cpu = "500m"
        memory = "512Mi"
        if "gpu" in t:
            cpu = "2000m"
            memory = "8Gi"

        return JobSpecRequest(
            prompt=text,
            name=name,
            image=image,
            command=command,
            cpu=cpu,
            memory=memory,
            namespace=namespace
        )

    def job_request_to_yaml(self, req: JobSpecRequest):
        cmd = ["/bin/sh", "-c", req.command]

        out = f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: {req.name}
  namespace: {req.namespace}
spec:
  template:
    metadata:
      labels:
        app: agentctl
    spec:
      restartPolicy: Never
      containers:
      - name: main
        image: {req.image}
        command:
          - {cmd[0]}
          - {cmd[1]}
          - {cmd[2]}
        resources:
          requests:
            cpu: {req.cpu}
            memory: {req.memory}
          limits:
            cpu: {req.cpu}
            memory: {req.memory}
"""
        return out

    def nl_to_job_yaml(self, text: str, namespace="default"):
        req = self.nl_to_job_request(text, namespace)
        return self.job_request_to_yaml(req)
