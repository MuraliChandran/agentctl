#!/usr/bin/env python3
"""
AgentCTL Gradio UI (Frontend)
Communicates with FastAPI backend instead of Kubernetes directly
"""

import os
import time
import requests
import gradio as gr

# -------------------------------------------------------------------
# Backend URL (FastAPI)
# -------------------------------------------------------------------
BACKEND_URL = os.getenv(
    "AGENTCTL_BACKEND_URL",
    "http://127.0.0.1:9000"  # default for local development
)

print(f"🔗 AgentCTL Backend URL: {BACKEND_URL}")

# Helper to join backend URL
def api(path: str) -> str:
    return f"{BACKEND_URL}{path}"


# -------------------------------------------------------------------
# API Client Helpers
# -------------------------------------------------------------------

def generate_yaml(prompt: str, namespace: str, kind: str) -> str:
    """Call FastAPI: POST /api/generate-yaml"""
    try:
        payload = {
            "prompt": prompt,
            "namespace": namespace,
            "kind": kind
        }
        r = requests.post(api("/api/generate-yaml"), json=payload)
        r.raise_for_status()
        return r.json().get("yaml", "# No YAML returned")
    except Exception as e:
        return f"# ERROR: {e}"


def apply_yaml(yaml_text: str) -> tuple[str, str]:
    """Call FastAPI: POST /api/apply"""
    try:
        r = requests.post(api("/api/apply"), json={"yaml": yaml_text})
        r.raise_for_status()
        data = r.json()
        return data.get("status", ""), data.get("raw", "")
    except Exception as e:
        return f"❌ ERROR: {e}", ""


def get_snapshot() -> str:
    """Call FastAPI: GET /api/snapshot"""
    try:
        r = requests.get(api("/api/snapshot"))
        r.raise_for_status()
        return r.json().get("snapshot", "No snapshot available")
    except Exception as e:
        return f"ERROR fetching snapshot: {e}"


def get_logs_once(pod_name: str, tail: int) -> str:
    """Call FastAPI: GET /api/logs"""
    try:
        params = {"pod_name": pod_name, "tail": tail}
        r = requests.get(api("/api/logs"), params=params)
        r.raise_for_status()
        return r.json().get("logs", "No logs received")
    except Exception as e:
        return f"<span style='color:red;'>ERROR: {e}</span>"


def follow_logs(pod_name: str, tail: int):
    """Streaming generator for follow logs."""
    while True:
        html = get_logs_once(pod_name, tail)
        yield html
        time.sleep(2)


# -------------------------------------------------------------------
# Gradio UI
# -------------------------------------------------------------------

def build_ui():
    with gr.Blocks(title="AgentCTL Frontend (FastAPI Backend)") as ui:

        gr.Markdown(f"""
# 🚀 AgentCTL (Frontend)
FastAPI Backend URL in use:

### **🔗 {BACKEND_URL}**

_(Set AGENTCTL_BACKEND_URL environment variable to override)_

---
""")

        # ----------------------------------------------------------
        # TAB 1 — Create Resource
        # ----------------------------------------------------------
        with gr.Tab("Create Resource"):
            with gr.Row():
                prompt = gr.Textbox(
                    label="Describe your resource",
                    lines=5,
                    placeholder=(
                        "Examples:\n"
                        "- run a python job to preprocess data\n"
                        "- create an nginx deployment with 3 replicas\n"
                        "- schedule a cleanup script every 5 minutes\n"
                    )
                )

                with gr.Column():
                    namespace = gr.Textbox(
                        label="Namespace",
                        value="default"
                    )
                    kind = gr.Dropdown(
                        label="Kind",
                        choices=["Auto", "Job", "Deployment", "CronJob"],
                        value="Auto"
                    )

            generate_btn = gr.Button("Generate YAML", variant="primary")
            yaml_box = gr.Code(label="Generated YAML", language="yaml")

            apply_btn = gr.Button("Apply YAML to Cluster", variant="primary")
            apply_status = gr.Textbox(label="Status")
            apply_raw = gr.Textbox(label="Raw API Response")

            generate_btn.click(
                fn=generate_yaml,
                inputs=[prompt, namespace, kind],
                outputs=yaml_box
            )

            apply_btn.click(
                fn=apply_yaml,
                inputs=[yaml_box],
                outputs=[apply_status, apply_raw]
            )

        # ----------------------------------------------------------
        # TAB 2 — Dashboard
        # ----------------------------------------------------------
        with gr.Tab("Cluster Dashboard"):
            refresh_button = gr.Button("Refresh Snapshot", variant="primary")
            snapshot_box = gr.Textbox(label="Cluster Snapshot", lines=25)

            refresh_button.click(fn=get_snapshot, outputs=snapshot_box)

        # ----------------------------------------------------------
        # TAB 3 — Pods Logs
        # ----------------------------------------------------------
        with gr.Tab("Pod Logs"):
            pod_name = gr.Textbox(label="Pod Name")
            tail_lines = gr.Slider(
                label="Tail Lines",
                minimum=10,
                maximum=500,
                value=100
            )

            get_logs_btn = gr.Button("Get Logs")
            follow_logs_btn = gr.Button("Follow Logs (Live)", variant="primary")
            logs_html = gr.HTML(label="Logs Terminal")

            get_logs_btn.click(
                fn=get_logs_once,
                inputs=[pod_name, tail_lines],
                outputs=logs_html
            )

            follow_logs_btn.click(
                fn=follow_logs,
                inputs=[pod_name, tail_lines],
                outputs=logs_html
            )

    return ui


# Build UI
app = build_ui()

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
