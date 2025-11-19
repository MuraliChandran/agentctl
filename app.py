#!/usr/bin/env python3

import os
import time
import re
import requests
import gradio as gr


# ---------------------------------------------------------------------
# Backend URL (FastAPI)
# ---------------------------------------------------------------------
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:9000")


def _post(path: str, payload: dict):
    """POST helper"""
    url = f"{BACKEND_URL}{path}"
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


def _get(path: str):
    """GET helper"""
    url = f"{BACKEND_URL}{path}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------
# Colorize Logs (same as before)
# ---------------------------------------------------------------------
def _colorize_logs(text: str) -> str:
    if not text:
        return "<span style='color:#888;'>No logs</span>"

    html = []
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
        html.append(f"<span style='color:{color};'>{safe}</span>")

    return "<br>".join(html)


# ---------------------------------------------------------------------
# UI Connected Functions (call backend)
# ---------------------------------------------------------------------

def generate_yaml(prompt: str, namespace: str, kind: str) -> str:
    payload = {
        "prompt": prompt,
        "namespace": namespace,
        "kind": kind
    }
    result = _post("/api/generate-yaml", payload)
    return result["yaml"]


def apply_yaml(yaml_text: str):
    payload = {"yaml": yaml_text}
    result = _post("/api/apply", payload)
    return result["status"], result["raw"]


def get_snapshot() -> str:
    result = _get("/api/snapshot")
    return result["snapshot"]


def get_logs_once(pod_name: str, tail: int) -> str:
    if not pod_name.strip():
        return "<span style='color:#ff4b4b;'>Enter a pod name</span>"

    result = _get(f"/api/logs?pod={pod_name}&tail={tail}")
    logs = result.get("logs", "")
    return _colorize_logs(logs)


def follow_logs(pod_name: str, tail: int):
    """Stream logs from backend."""
    if not pod_name.strip():
        yield "<span style='color:#ff4b4b;'>Enter a pod name</span>"
        return

    while True:
        result = _get(f"/api/logs?pod={pod_name}&tail={tail}")
        logs = result.get("logs", "")
        yield _colorize_logs(logs)
        time.sleep(2)


# ---------------------------------------------------------------------
# CSS (same as before)
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
# UI (identical to original UI)
# ---------------------------------------------------------------------

def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="AgentCTL: LLM-Driven Kubernetes Automation",
        css=TERMINAL_CSS
    ) as demo:

        gr.Markdown(f"""
### 🔧 Environment

Connected to backend: **{BACKEND_URL}**

- `K8S_API_BASE_URL` (backend)
- `K8S_NAMESPACE`  
- K8s proxy + FastAPI → ngrok → HuggingFace  
---
""")

        # CREATE RESOURCE TAB
        with gr.Tab("Create Resource"):
            with gr.Row():
                prompt = gr.Textbox(
                    label="Describe resource",
                    lines=5,
                    placeholder=(
                        "- run a python job\n"
                        "- 3-replica nginx deployment\n"
                        "- cronjob every 5 minutes"
                    ),
                )

                with gr.Column():
                    namespace = gr.Textbox(
                        label="Namespace",
                        value="default"
                    )
                    kind = gr.Dropdown(
                        label="Resource kind",
                        choices=["Auto", "Job", "Deployment", "CronJob"],
                        value="Auto",
                    )

            gen_btn = gr.Button("Generate YAML", variant="primary")
            yaml_box = gr.Code(language="yaml", lines=22, label="Generated YAML")

            apply_btn = gr.Button("Apply to cluster")
            apply_msg = gr.Textbox(label="Status")
            apply_raw = gr.Textbox(label="API Raw Response")

            gen_btn.click(
                generate_yaml,
                inputs=[prompt, namespace, kind],
                outputs=yaml_box
            )

            apply_btn.click(
                apply_yaml,
                inputs=[yaml_box],
                outputs=[apply_msg, apply_raw]
            )

        # DASHBOARD
        with gr.Tab("Cluster Dashboard"):
            snap_btn = gr.Button("Refresh snapshot", variant="primary")
            snap_box = gr.Textbox(lines=25, label="Cluster Overview")

            snap_btn.click(
                get_snapshot,
                inputs=[],
                outputs=snap_box
            )

        # LOGS TAB
        with gr.Tab("Pod Logs"):
            pod_name = gr.Textbox(label="Pod Name")
            tail = gr.Slider(10, 500, value=100, step=10, label="Tail lines")

            logs_btn = gr.Button("Get logs once")
            follow_btn = gr.Button("Follow logs (live)", variant="primary")

            logs_box = gr.HTML(elem_id="logs_terminal", label="Logs")

            logs_btn.click(
                get_logs_once,
                inputs=[pod_name, tail],
                outputs=logs_box
            )

            follow_btn.click(
                follow_logs,
                inputs=[pod_name, tail],
                outputs=logs_box
            )

    return demo


app = build_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    app.launch(server_name="0.0.0.0", server_port=port)
