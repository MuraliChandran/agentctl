#!/usr/bin/env python3

import os
import re
import time
from typing import Tuple

import gradio as gr

from agentctl.config import settings
from agentctl.k8s_client import K8sClient
from agentctl.agent import K8sAgent


# ---------------------------------------------------------------------
# Core objects
# ---------------------------------------------------------------------

agent = K8sAgent()


def _get_client() -> K8sClient:
    """Create a Kubernetes HTTP client using env-based config."""
    return K8sClient()


# ---------------------------------------------------------------------
# YAML generation + apply
# ---------------------------------------------------------------------


def generate_yaml_from_prompt(prompt: str, namespace: str, kind: str) -> str:
    """Convert natural language + kind selection into YAML."""
    if not prompt.strip():
        return "# Enter a description, e.g. 'run a python preprocessing job'"

    ns = namespace.strip() or settings.k8s_namespace
    kind_sel = None if kind == "Auto" else kind

    _, yaml_text = agent.nl_to_resource_yaml(
        prompt,
        namespace=ns,
        kind=kind_sel,
    )
    return yaml_text


def apply_yaml_to_cluster(yaml_text: str) -> Tuple[str, str]:
    """Apply a YAML manifest to the cluster via K8s API."""
    if not yaml_text.strip():
        return "No YAML to apply.", ""

    client = _get_client()
    result = client.apply_manifest(yaml_text)

    raw_str = ""
    if result.raw_response is not None:
        try:
            raw_str = str(result.raw_response)
        except Exception:
            raw_str = "<unserialisable response>"

    prefix = "✅" if result.success else "❌"
    return f"{prefix} {result.message}", raw_str


# ---------------------------------------------------------------------
# Dashboard snapshot
# ---------------------------------------------------------------------


def get_cluster_snapshot() -> str:
    """Return a human-readable snapshot of Jobs, Pods, Deployments, CronJobs."""
    client = _get_client()
    snap = client.snapshot()

    lines: list[str] = [f"Namespace: {snap.namespace}", ""]

    # Jobs
    lines.append("Jobs:")
    if not snap.jobs:
        lines.append("  (no jobs)")
    else:
        for j in snap.jobs:
            lines.append(
                f"  - {j.name}: succeeded={j.succeeded}, "
                f"failed={j.failed}, active={j.active}"
            )

    # Pods
    lines.append("")
    lines.append("Pods:")
    if not snap.pods:
        lines.append("  (no pods)")
    else:
        for p in snap.pods:
            lines.append(f"  - {p.name}: phase={p.phase}")

    # Deployments
    lines.append("")
    lines.append("Deployments:")
    if not snap.deployments:
        lines.append("  (no deployments)")
    else:
        for d in snap.deployments:
            lines.append(
                f"  - {d.name}: replicas={d.replicas}, ready={d.ready}"
            )

    # CronJobs
    lines.append("")
    lines.append("CronJobs:")
    if not snap.cronjobs:
        lines.append("  (no cronjobs)")
    else:
        for c in snap.cronjobs:
            last = c.last_schedule or "never"
            lines.append(
                f"  - {c.name}: active={c.active}, lastScheduleTime={last}"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------
# Logs helpers (colorised terminal + live follow)
# ---------------------------------------------------------------------


def _fetch_pod_logs_raw(pod_name: str, tail_lines: int) -> str:
    """Internal: raw log text from Kubernetes."""
    client = _get_client()
    return client.get_pod_logs(pod_name.strip(), tail_lines=tail_lines)


def _colorize_logs(text: str) -> str:
    """Convert log text into HTML with basic severity colouring."""
    if not text:
        return "<span style='color:#888;'>No logs</span>"

    lines = text.splitlines()
    out: list[str] = []

    for line in lines:
        if re.search(r"(error|failed|exception)", line, re.IGNORECASE):
            colour = "#ff4b4b"  # red
        elif re.search(r"(warn)", line, re.IGNORECASE):
            colour = "#f7c843"  # yellow
        elif re.search(r"(info|started|running|completed)", line, re.IGNORECASE):
            colour = "#5ad55a"  # green
        else:
            colour = "#d0d0d0"  # grey

        safe = line.replace("<", "&lt;").replace(">", "&gt;")
        out.append(f"<span style='color:{colour};'>{safe}</span>")

    return "<br>".join(out)


def get_pod_logs_once(pod_name: str, tail_lines: int) -> str:
    """One-shot logs fetch, used for the 'Get logs' button."""
    pod_name = pod_name.strip()
    if not pod_name:
        return "<span style='color:#ff4b4b;'>Enter a pod name from the dashboard.</span>"

    raw = _fetch_pod_logs_raw(pod_name, tail_lines)
    return _colorize_logs(raw)


def follow_pod_logs(pod_name: str, tail_lines: int):
    """Live streaming logs using Gradio generator output."""
    pod_name = pod_name.strip()
    if not pod_name:
        yield "<span style='color:#ff4b4b;'>Enter a pod name from the dashboard.</span>"
        return

    while True:
        raw = _fetch_pod_logs_raw(pod_name, tail_lines)
        html = _colorize_logs(raw)
        yield html
        time.sleep(2)


# CSS for the logs "terminal"
TERMINAL_CSS = """
#logs_terminal {
    background-color: #111111 !important;
    color: #d0d0d0 !important;
    font-family: monospace !important;
    padding: 14px;
    border-radius: 8px;
    border: 1px solid #444444;
    height: 420px;
    overflow-y: scroll;
    white-space: pre-wrap;
}
"""


# ---------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------


def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="AgentCTL: LLM-Driven Kubernetes Automation",
        css=TERMINAL_CSS,
    ) as demo:
        # Top environment hint (like your screenshot)
        gr.Markdown(
            """
### 🔧 Environment configuration

- `K8S_API_BASE_URL` → **public K8s API URL** (ngrok / Cloudflare tunnel over `kubectl proxy`)
- `K8S_NAMESPACE` → **default namespace** (e.g. `default`)
- `K8S_VERIFY_SSL` → **true/false** (set `false` for self-signed ngrok endpoints)
- `AGENTCTL_USE_LLM` → **true/false** (optional; uses OpenAI if enabled in `agent.py`)
- `OPENAI_API_KEY` → your key (if LLM mode enabled)

---
"""
        )

        # ============================================================
        # Create Resource tab
        # ============================================================
        with gr.Tab("Create Resource"):
            with gr.Row():
                prompt = gr.Textbox(
                    label="Describe the resource you want",
                    placeholder=(
                        "Examples:\n"
                        "- run a python job to preprocess data\n"
                        "- create an nginx deployment with 3 replicas\n"
                        "- schedule a python cleanup job every 5 minutes\n"
                    ),
                    lines=5,
                )

                with gr.Column():
                    namespace = gr.Textbox(
                        label="Kubernetes namespace",
                        value=settings.k8s_namespace,
                        lines=1,
                    )
                    kind = gr.Dropdown(
                        label="Resource kind",
                        choices=["Auto", "Job", "Deployment", "CronJob"],
                        value="Auto",
                    )
                    gr.Markdown(
                        "Tip: leave **Auto** to let the agent infer Job vs Deployment vs CronJob."
                    )

            generate_btn = gr.Button("Generate YAML", variant="primary")
            yaml_box = gr.Code(
                label="Generated manifest (YAML)",
                language="yaml",
                lines=22,
            )

            apply_btn = gr.Button("Apply to cluster")
            apply_msg = gr.Textbox(label="Status", interactive=False)
            apply_raw = gr.Textbox(label="Raw API response (debug)")

            generate_btn.click(
                fn=generate_yaml_from_prompt,
                inputs=[prompt, namespace, kind],
                outputs=yaml_box,
            )

            apply_btn.click(
                fn=apply_yaml_to_cluster,
                inputs=[yaml_box],
                outputs=[apply_msg, apply_raw],
            )

        # ============================================================
        # Cluster Dashboard tab
        # ============================================================
        with gr.Tab("Cluster Dashboard"):
            gr.Markdown(
                "Snapshot of **Jobs, Pods, Deployments, CronJobs** in the target namespace."
            )
            snapshot_btn = gr.Button("Refresh snapshot", variant="primary")
            snapshot_box = gr.Textbox(
                label="Cluster overview",
                lines=25,
                interactive=False,
            )

            snapshot_btn.click(
                fn=get_cluster_snapshot,
                inputs=[],
                outputs=[snapshot_box],
            )

        # ============================================================
        # Pod Logs tab
        # ============================================================
        with gr.Tab("Pod Logs"):
            gr.Markdown(
                "Paste a pod name from the **Cluster Dashboard** (e.g. `agentctl-job-lnrcp`) "
                "and fetch its logs. Use **Follow logs** for a live `kubectl logs -f` style view."
            )

            pod_name = gr.Textbox(
                label="Pod name",
                placeholder="e.g. preprocess-job-z48rz",
            )
            tail_lines = gr.Slider(
                label="Tail lines",
                minimum=10,
                maximum=500,
                step=10,
                value=100,
            )

            with gr.Row():
                get_logs_btn = gr.Button("Get logs once")
                follow_logs_btn = gr.Button("Follow logs (live)", variant="primary")

            logs_box = gr.HTML(label="Logs", elem_id="logs_terminal")

            get_logs_btn.click(
                fn=get_pod_logs_once,
                inputs=[pod_name, tail_lines],
                outputs=[logs_box],
            )
            
            follow_logs_btn.click(
                fn=follow_pod_logs,
                inputs=[pod_name, tail_lines],
                outputs=logs_box,
            )

    return demo


app = build_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    app.launch(server_name="0.0.0.0", server_port=port)
