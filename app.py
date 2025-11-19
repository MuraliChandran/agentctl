#!/usr/bin/env python3

import os
import re
import time
import uuid
import yaml
from typing import Tuple

import gradio as gr

from agentctl.config import settings
from agentctl.k8s_client import K8sClient
from agentctl.agent import K8sAgent


# ---------------------------------------------------------------------
# Core - Agent + Client
# ---------------------------------------------------------------------

agent = K8sAgent()

def _get_client() -> K8sClient:
    return K8sClient()


# ---------------------------------------------------------------------
# Unique Name Injection
# ---------------------------------------------------------------------

def _inject_unique_name(yaml_text: str) -> str:
    """
    Add unique suffix to metadata.name for Job, Deployment, CronJob.
    Prevents 409 AlreadyExists errors.
    """
    try:
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return yaml_text

        kind = data.get("kind")
        if kind not in {"Job", "CronJob", "Deployment"}:
            return yaml_text

        base = data["metadata"]["name"]
        suffix = str(uuid.uuid4())[:5]
        new_name = f"{base}-{suffix}"
        data["metadata"]["name"] = new_name

        # Patch CronJob template labels
        if kind == "CronJob":
            jt = data["spec"]["jobTemplate"]["spec"]["template"]
            if "metadata" in jt:
                if "labels" in jt["metadata"]:
                    jt["metadata"]["labels"]["app"] = new_name
                else:
                    jt["metadata"]["labels"] = {"app": new_name}

        return yaml.safe_dump(data)

    except Exception:
        return yaml_text


# ---------------------------------------------------------------------
# YAML Generation + Apply
# ---------------------------------------------------------------------

def generate_yaml_from_prompt(prompt: str, namespace: str, kind: str) -> str:
    if not prompt.strip():
        return "# Enter a description, e.g. 'run a python preprocessing job'"

    ns = namespace.strip() or settings.k8s_namespace
    kind_sel = None if kind == "Auto" else kind

    _, yaml_text = agent.nl_to_resource_yaml(prompt, namespace=ns, kind=kind_sel)
    return yaml_text


def apply_yaml_to_cluster(yaml_text: str) -> Tuple[str, str]:
    if not yaml_text.strip():
        return "No YAML to apply.", ""

    # Add unique suffix before applying
    yaml_text = _inject_unique_name(yaml_text)

    client = _get_client()
    result = client.apply_manifest(yaml_text)

    try:
        raw = str(result.raw_response)
    except:
        raw = "<unserialisable>"

    prefix = "✅" if result.success else "❌"
    return f"{prefix} {result.message}", raw


# ---------------------------------------------------------------------
# Cluster Snapshot
# ---------------------------------------------------------------------

def get_cluster_snapshot() -> str:
    client = _get_client()
    snap = client.snapshot()

    out = [f"Namespace: {snap.namespace}", ""]

    out.append("Jobs:")
    if not snap.jobs:
        out.append("  (no jobs)")
    else:
        for j in snap.jobs:
            out.append(
                f"  - {j.name}: succeeded={j.succeeded}, failed={j.failed}, active={j.active}"
            )

    out.append("")
    out.append("Pods:")
    if not snap.pods:
        out.append("  (no pods)")
    else:
        for p in snap.pods:
            out.append(f"  - {p.name}: phase={p.phase}")

    out.append("")
    out.append("Deployments:")
    if not snap.deployments:
        out.append("  (no deployments)")
    else:
        for d in snap.deployments:
            out.append(f"  - {d.name}: replicas={d.replicas}, ready={d.ready}")

    out.append("")
    out.append("CronJobs:")
    if not snap.cronjobs:
        out.append("  (no cronjobs)")
    else:
        for c in snap.cronjobs:
            last = c.last_schedule or "never"
            out.append(f"  - {c.name}: active={c.active}, lastScheduleTime={last}")

    return "\n".join(out)


# ---------------------------------------------------------------------
# Logs System
# ---------------------------------------------------------------------

def _colorize_logs(text: str) -> str:
    if not text:
        return "<span style='color:#888;'>No logs</span>"

    html_lines = []
    for line in text.splitlines():
        if re.search(r"(error|failed|exception)", line, re.IGNORECASE):
            color = "#ff4b4b"
        elif re.search(r"warn", line, re.IGNORECASE):
            color = "#f7c843"
        elif re.search(r"(info|started|running|completed)", line, re.IGNORECASE):
            color = "#5ad55a"
        else:
            color = "#d0d0d0"

        safe = line.replace("<", "&lt;").replace(">", "&gt;")
        html_lines.append(f"<span style='color:{color};'>{safe}</span>")

    return "<br>".join(html_lines)


def get_pod_logs_once(pod_name: str, tail_lines: int) -> str:
    pod_name = pod_name.strip()
    if not pod_name:
        return "<span style='color:#ff4b4b;'>Enter a pod name.</span>"

    client = _get_client()
    raw = client.get_pod_logs(pod_name, tail_lines)
    return _colorize_logs(raw)


def follow_pod_logs(pod_name: str, tail_lines: int):
    pod_name = pod_name.strip()
    if not pod_name:
        yield "<span style='color:#ff4b4b;'>Enter a pod name.</span>"
        return

    client = _get_client()
    while True:
        raw = client.get_pod_logs(pod_name, tail_lines)
        yield _colorize_logs(raw)
        time.sleep(2)


# ---------------------------------------------------------------------
# Logs CSS
# ---------------------------------------------------------------------

TERMINAL_CSS = """
#logs_terminal {
    background-color: #111;
    color: #ddd;
    font-family: monospace;
    padding: 14px;
    border-radius: 8px;
    border: 1px solid #444;
    height: 420px;
    overflow-y: scroll;
    white-space: pre-wrap;
}
"""


# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------

def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="AgentCTL: LLM-Driven Kubernetes Automation",
        css=TERMINAL_CSS,
    ) as demo:

        gr.Markdown("""
### 🔧 Environment
- `K8S_API_BASE_URL`  
- `K8S_NAMESPACE`  
- `K8S_VERIFY_SSL`  
- `OPENAI_API_KEY` (optional)
---
""")

        # -----------------------------------------------------------------
        # Create Resource
        # -----------------------------------------------------------------
        with gr.Tab("Create Resource"):
            with gr.Row():
                prompt = gr.Textbox(
                    label="Describe the resource",
                    placeholder=(
                        "- run a python job\n"
                        "- create an nginx deployment with 3 replicas\n"
                        "- schedule a cleanup script every 5 minutes\n"
                    ),
                    lines=5,
                )

                with gr.Column():
                    namespace = gr.Textbox(
                        label="Namespace",
                        value=settings.k8s_namespace,
                    )
                    kind = gr.Dropdown(
                        label="Resource kind",
                        choices=["Auto", "Job", "Deployment", "CronJob"],
                        value="Auto",
                    )

            generate_btn = gr.Button("Generate YAML", variant="primary")
            yaml_box = gr.Code(language="yaml", lines=22, label="Generated YAML")

            apply_btn = gr.Button("Apply to cluster")
            apply_msg = gr.Textbox(label="Status")
            apply_debug = gr.Textbox(label="Raw API Response")

            generate_btn.click(
                generate_yaml_from_prompt,
                inputs=[prompt, namespace, kind],
                outputs=yaml_box,
            )
            apply_btn.click(
                apply_yaml_to_cluster,
                inputs=[yaml_box],
                outputs=[apply_msg, apply_debug],
            )

        # -----------------------------------------------------------------
        # Dashboard
        # -----------------------------------------------------------------
        with gr.Tab("Cluster Dashboard"):
            snapshot_btn = gr.Button("Refresh snapshot", variant="primary")
            snapshot_box = gr.Textbox(lines=25, label="Cluster Overview")

            snapshot_btn.click(
                get_cluster_snapshot,
                inputs=[],
                outputs=snapshot_box,
            )

        # -----------------------------------------------------------------
        # Logs
        # -----------------------------------------------------------------
        with gr.Tab("Pod Logs"):
            pod_name = gr.Textbox(label="Pod name")
            tail_lines = gr.Slider(10, 500, step=10, value=100, label="Tail lines")

            get_logs_btn = gr.Button("Get logs once")
            follow_logs_btn = gr.Button("Follow logs (live)", variant="primary")

            logs_box = gr.HTML(elem_id="logs_terminal", label="Logs")

            get_logs_btn.click(
                get_pod_logs_once,
                inputs=[pod_name, tail_lines],
                outputs=logs_box,
            )

            follow_logs_btn.click(
                follow_pod_logs,
                inputs=[pod_name, tail_lines],
                outputs=logs_box,
                stream=True,
            )

    return demo


app = build_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    app.launch(server_name="0.0.0.0", server_port=port)
