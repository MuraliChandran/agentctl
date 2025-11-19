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

print(f"AgentCTL Backend URL: {BACKEND_URL}")

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
        # Backend sends message + raw
        message = data.get("message", "")
        raw = data.get("raw", "")
        return message, raw
    except Exception as e:
        return f"ERROR: {e}", ""

def run_agent(instruction: str, namespace: str, kind: str):
    """Call FastAPI: POST /api/agent"""
    try:
        payload = {
            "instruction": instruction,
            "namespace": namespace,
            "kind": kind
        }
        r = requests.post(api("/api/agent"), json=payload)
        r.raise_for_status()

        data = r.json()
        return (
            data.get("yaml", "# No YAML"), 
            data.get("result", {})
        )
    except Exception as e:
        return f"# ERROR: {e}", {}

# -------------------------------------------------------------------
# Snapshot Formatter (Emoji-Free)
# -------------------------------------------------------------------

def format_snapshot(data):
    lines = []

    lines.append(f"Namespace: {data.get('namespace','default')}\n")
    lines.append("==== JOBS ====\n")

    for job in data.get("jobs", []):
        if job["succeeded"] > 0:
            status = "Completed"
        elif job["failed"] > 0:
            status = "Failed"
        elif job["active"] > 0:
            status = "Active"
        else:
            status = "Pending"

        lines.append(
            f"{job['name']}: {status} | Active={job['active']} | Success={job['succeeded']} | Failed={job['failed']}"
        )

    lines.append("\n==== PODS ====\n")

    for pod in data.get("pods", []):
        phase = pod["phase"]
        lines.append(f"{pod['name']}: {phase}")

    lines.append("\n==== CRONJOBS ====\n")

    for cj in data.get("cronjobs", []):
        lines.append(
            f"{cj['name']}: Active={cj['active']} | LastSchedule={cj['last_schedule']}"
        )

    return "\n".join(lines)


def get_logs_once(pod_name: str, tail: int) -> str:
    """Call FastAPI: GET /api/logs"""
    try:
        params = {"pod_name": pod_name, "tail": tail}
        r = requests.get(api("/api/logs"), params=params)
        r.raise_for_status()
        return r.json().get("logs", "No logs received")
    except Exception as e:
        return f"ERROR: {e}"


def follow_logs(pod_name: str, tail: int):
    """Streaming logs (auto-refresh every 2s)"""
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
# AgentCTL (Frontend)

Backend URL in use:
**{BACKEND_URL}**

Set `AGENTCTL_BACKEND_URL` to override.
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
                    namespace = gr.Textbox(label="Namespace", value="default")
                    kind = gr.Dropdown(
                        label="Kind",
                        choices=["Auto", "Job", "Deployment", "CronJob"],
                        value="Auto"
                    )

            generate_btn = gr.Button("Generate YAML")
            yaml_box = gr.Code(label="Generated YAML", language="yaml")

            apply_btn = gr.Button("Apply YAML to Cluster")
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
        # TAB 2 — Cluster Dashboard
        # ----------------------------------------------------------
        with gr.Tab("Cluster Dashboard"):
            refresh_button = gr.Button("Refresh Snapshot")
            snapshot_box = gr.Textbox(label="Cluster Snapshot", lines=25)

            def get_formatted_snapshot():
                try:
                    r = requests.get(api("/api/snapshot"))
                    r.raise_for_status()
                    data = r.json()
                    return format_snapshot(data)
                except Exception as e:
                    return f"ERROR fetching snapshot: {e}"

            refresh_button.click(
                fn=get_formatted_snapshot,
                outputs=snapshot_box
            )

        # ----------------------------------------------------------
        # TAB 3 — Pod Logs
        # ----------------------------------------------------------
        with gr.Tab("Pod Logs"):
            pod_name = gr.Textbox(label="Pod Name")
            tail_lines = gr.Slider(
                label="Tail Lines", minimum=10, maximum=500, value=100
            )

            get_logs_btn = gr.Button("Get Logs")
            follow_logs_btn = gr.Button("Follow Logs (Live)")
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

        # ----------------------------------------------------------
        # TAB 4 — Agent Mode (LLM → YAML → Apply)
        # ----------------------------------------------------------
        with gr.Tab("Agent Mode"):
            gr.Markdown("""
                ## Agentic LLM Mode
                Enter natural language instructions and let the backend agent:
                1. Plan the Kubernetes operation  
                2. Generate YAML (LLM → fallback → validated)
                3. Apply it to the cluster  
                """)

            instruction = gr.Textbox(
                label="Instruction",
                lines=4,
                placeholder="e.g. deploy a pytorch training job with 1 GPU"
            )

            namespace2 = gr.Textbox(
                label="Namespace",
                value="default"
            )

            kind2 = gr.Dropdown(
                label="Kind Override (optional)",
                choices=["Auto", "Job", "Deployment", "CronJob"],
                value="Auto"
            )

            run_btn = gr.Button("Run Agent")

            agent_yaml = gr.Code(label="Generated YAML", language="yaml")
            agent_result = gr.JSON(label="API Apply Result")

            run_btn.click(
                fn=run_agent,
                inputs=[instruction, namespace2, kind2],
                outputs=[agent_yaml, agent_result]
            )

    return ui


# Build UI
app = build_ui()

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
