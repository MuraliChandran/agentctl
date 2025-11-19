"""Natural language → Kubernetes YAML generator (Job / Deployment / CronJob).

Heuristic templates + optional LLM (OpenAI) for richer YAML.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import os
import re

# Optional LLM support (OpenAI)
try:
    from openai import OpenAI  # pip install openai
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


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
    """Agent that turns NL into Job / Deployment / CronJob YAML."""

    # --------------------- Kind detection --------------------- #

    def infer_kind(self, text: str) -> str:
        t = text.lower()

        # CronJob-ish language
        if any(w in t for w in ["every minute", "every 5 minutes", "every hour", "cron", "schedule", "scheduled job"]):
            return "CronJob"

        # Deployment-ish language
        if any(w in t for w in ["deployment", "service", "web", "api", "server", "nginx", "frontend", "backend"]):
            return "Deployment"

        # Default to Job
        return "Job"

    # --------------------- Job templates --------------------- #

    def nl_to_job_request(self, text: str, namespace: str = "default") -> JobSpecRequest:
        t = text.lower()
        name = "agentctl-job"

        if "preprocess" in t:
            name = "preprocess-job"
        elif "inference" in t:
            name = "inference-job"
        elif "train" in t or "training" in t:
            name = "training-job"

        image = "busybox:1.36"
        if "python" in t:
            image = "python:3.11-slim"
        if "pytorch" in t:
            image = "pytorch/pytorch:2.3.0-cuda12.1-cudnn9-runtime"

        command = "echo Hello && sleep 5"
        if "run python" in t:
            idx = t.find("run python")
            if idx != -1:
                # everything from "python" onwards becomes the command
                fragment = text[idx:].replace("run ", "").strip()
                command = fragment

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
            namespace=namespace,
        )

    def job_request_to_yaml(self, req: JobSpecRequest) -> str:
        cmd = ["/bin/sh", "-c", req.command] if req.command else None

        lines = [
            "apiVersion: batch/v1",
            "kind: Job",
            "metadata:",
            f"  name: {req.name}",
            f"  namespace: {req.namespace}",
            "spec:",
            "  template:",
            "    metadata:",
            "      labels:",
            "        app: agentctl",
            "    spec:",
            "      restartPolicy: Never",
            "      containers:",
            "        - name: main",
            f"          image: {req.image}",
        ]
        if cmd:
            lines.append("          command:")
            for c in cmd:
                lines.append(f"            - {c}")
        lines.extend(
            [
                "          resources:",
                "            requests:",
                f"              cpu: {req.cpu}",
                f"              memory: {req.memory}",
                "            limits:",
                f"              cpu: {req.cpu}",
                f"              memory: {req.memory}",
            ]
        )
        return "\n".join(lines) + "\n"

    # --------------------- Deployment template --------------------- #

    def nl_to_deployment_yaml(self, text: str, namespace: str = "default") -> str:
        t = text.lower()
        name = "agentctl-deployment"
        image = "nginx:1.27-alpine"
        replicas = 1

        if "nginx" in t:
            name = "nginx-deployment"
        if "python" in t:
            image = "python:3.11-slim"
        if "pytorch" in t:
            image = "pytorch/pytorch:2.3.0-cuda12.1-cudnn9-runtime"

        m = re.search(r"(\d+)\s+replica", t)
        if m:
            replicas = int(m.group(1))

        lines = [
            "apiVersion: apps/v1",
            "kind: Deployment",
            "metadata:",
            f"  name: {name}",
            f"  namespace: {namespace}",
            "  labels:",
            "    app: agentctl-deployment",
            "spec:",
            f"  replicas: {replicas}",
            "  selector:",
            "    matchLabels:",
            "      app: agentctl-deployment",
            "  template:",
            "    metadata:",
            "      labels:",
            "        app: agentctl-deployment",
            "    spec:",
            "      containers:",
            "        - name: main",
            f"          image: {image}",
            "          ports:",
            "            - containerPort: 80",
        ]
        return "\n".join(lines) + "\n"

    # --------------------- CronJob template --------------------- #

    def nl_to_cronjob_yaml(self, text: str, namespace: str = "default") -> str:
        t = text.lower()
        name = "agentctl-cronjob"
        image = "busybox:1.36"
        command = "echo Hello from CronJob && date"
        schedule = "*/5 * * * *"  # default every 5 minutes

        if "every minute" in t:
            schedule = "* * * * *"
        elif "every 5 minutes" in t:
            schedule = "*/5 * * * *"
        elif "every hour" in t:
            schedule = "0 * * * *"
        elif "every day" in t:
            schedule = "0 0 * * *"

        if "python" in t:
            image = "python:3.11-slim"
        if "run python" in t:
            idx = t.find("run python")
            fragment = text[idx:].replace("run ", "").strip()
            command = fragment

        lines = [
            "apiVersion: batch/v1",
            "kind: CronJob",
            "metadata:",
            f"  name: {name}",
            f"  namespace: {namespace}",
            "spec:",
            f"  schedule: \"{schedule}\"",
            "  jobTemplate:",
            "    spec:",
            "      template:",
            "        metadata:",
            "          labels:",
            "            app: agentctl-cronjob",
            "        spec:",
            "          restartPolicy: Never",
            "          containers:",
            "            - name: main",
            f"              image: {image}",
            "              command:",
            "                - /bin/sh",
            "                - -c",
            f"                - {command}",
        ]
        return "\n".join(lines) + "\n"

    # --------------------- Optional OpenAI LLM --------------------- #

    def maybe_llm_yaml(self, text: str, kind: str, namespace: str, fallback_yaml: str) -> str:
        """If AGENTCTL_USE_LLM=true and OpenAI is configured, ask the LLM
        to generate/clean YAML. Otherwise return fallback_yaml.
        """
        use_llm = os.getenv("AGENTCTL_USE_LLM", "false").lower() == "true"
        api_key = os.getenv("OPENAI_API_KEY")

        if not use_llm or not api_key or OpenAI is None:
            return fallback_yaml

        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        system_msg = (
            "You are an expert Kubernetes engineer. "
            "Given a natural language request, output a single valid Kubernetes "
            f"{kind} manifest in YAML. Do not include explanations or code fences."
        )

        user_msg = (
            f"Namespace: {namespace}\n"
            f"Kind: {kind}\n"
            f"Request: {text}\n\n"
            "Start from this template and improve it if needed:\n"
            f"{fallback_yaml}"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
        )
        content = resp.choices[0].message.content or fallback_yaml

        # Strip ```yaml fences if present
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z]*", "", content).strip()
            if content.endswith("```"):
                content = content[:-3].strip()

        return content

    # --------------------- Public entrypoint --------------------- #

    def nl_to_resource_yaml(
        self,
        text: str,
        namespace: str = "default",
        kind: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Return (kind, yaml) for a given prompt."""
        if not kind or kind.lower() == "auto":
            kind = self.infer_kind(text)

        if kind == "Job":
            req = self.nl_to_job_request(text, namespace)
            base_yaml = self.job_request_to_yaml(req)
        elif kind == "Deployment":
            base_yaml = self.nl_to_deployment_yaml(text, namespace)
        elif kind == "CronJob":
            base_yaml = self.nl_to_cronjob_yaml(text, namespace)
        else:
            raise ValueError(f"Unsupported kind: {kind}")

        final_yaml = self.maybe_llm_yaml(text, kind=kind, namespace=namespace, fallback_yaml=base_yaml)
        return kind, final_yaml
