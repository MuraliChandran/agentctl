#!/usr/bin/env python3

import os
from typing import Tuple

import gradio as gr

from agentctl.config import settings
from agentctl.k8s_client import K8sClient
from agentctl.agent import K8sAgent


agent = K8sAgent()


def _get_client() -> K8sClient:
    return K8sClient()


# ------------------------------------------------------------
# Handlers
# ------------------------------------------------------------


def generate_yaml_from_prompt(prompt: str, namespace: str, kind: str) -> str:
    if not prompt.strip():
        return "# Enter a description, e.g. 'run a python preprocessing job'"
    _, yaml_text = agent.nl_to_resource_yaml(
        prompt,
        namespace=namespace or settings.k8s_namespace,
        kind=kind if kind != "Auto" else None,
    )
    return yaml_text


def apply_yaml_to_cluster(yaml_text: str) -> Tuple[str, str]:
    if not yaml_text.strip():
        return "No YAML to apply.", ""

    client = _get_client()
    result = client.apply_manifest(yaml_text)

    if result.success:
        return result.message, (result.raw_response and str(result.raw_response) or "")
    else:
        return f"❌ {result.message}", (result.raw_response and str(result.raw_response) or "")


def get_cluster_snapshot() -> str:
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
                f"  - {j.name}: succeeded={j.succeeded}, failed={j.failed}, active={j.active}"
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


def get_pod_logs_handler(pod_name: str, tail_lines: int) -> str:
    if not pod_name.strip():
        return "Enter a pod name from the snapshot above."
    client = _get_client()
    logs = client.get_pod_logs(pod_name.strip(), tail_lines=tail_lines)
    return logs


# ------------------------------------------------------------
# Gradio UI
# ------------------------------------------------------------


def build_app() -> gr.Blocks:
    with gr.Blocks(title="AgentCTL: LLM-Driven Kubernetes Automation") as demo:
        gr.Markdown(
            """
            # AgentCTL: LLM-Driven Kubernetes Automation

            This Space connects to a **real Kubernetes cluster** (e.g. Minikube
            exposed via `kubectl proxy` + ngrok). It demonstrates an
            **agentic workflow** where natural language is converted into
            Kubernetes Job / Deployment / CronJob manifests.

            Environment variables:

            - `K8S_API_BASE_URL` → public K8s API URL (ngrok over `kubectl proxy`)
            - `K8S_NAMESPACE`    → default namespace
            - `K8S_VERIFY_SSL`   → true/false
            - `AGENTCTL_USE_LLM` → true/false (optional; uses OpenAI if enabled)
            - `OPENAI_API_KEY`   → your key (if LLM enabled)
            """
        )

        # --------- Create Resource tab --------- #
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

            generate_btn = gr.Button("Generate YAML")
            yaml_box = gr.Code(label="Generated Manifest (YAML)", language="yaml", lines=22)

            apply_btn = gr.Button("Apply to Cluster")
            apply_msg = gr.Textbox(label="Status", interactive=False)
            apply_raw = gr.Textbox(label="Raw API response (debug)")

            generate_btn.click(
                fn=generate_yaml_from_prompt,
                inputs=[prompt, namespace, kind],
                outputs=[yaml_box],
            )

            apply_btn.click(
                fn=apply_yaml_to_cluster,
                inputs=[yaml_box],
                outputs=[apply_msg, apply_raw],
            )

        # --------- Dashboard tab --------- #
        with gr.Tab("Cluster Dashboard"):
            gr.Markdown("Snapshot of Jobs, Pods, Deployments and CronJobs in the namespace.")
            snapshot_btn = gr.Button("Refresh snapshot")
            snapshot_box = gr.Textbox(label="Cluster Overview", lines=25)

            snapshot_btn.click(fn=get_cluster_snapshot, inputs=[], outputs=[snapshot_box])

        # --------- Pod Logs tab --------- #
        with gr.Tab("Pod Logs"):
            pod_name = gr.Textbox(label="Pod name")
            tail_lines = gr.Slider(
                label="Tail lines",
                minimum=10,
                maximum=500,
                step=10,
                value=100,
            )
            logs_btn = gr.Button("Get logs")
            logs_box = gr.Textbox(label="Logs", lines=25)

            logs_btn.click(
                fn=get_pod_logs_handler,
                inputs=[pod_name, tail_lines],
                outputs=[logs_box],
            )

    return demo


app = build_app()

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", 7860)))
