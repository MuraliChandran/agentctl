#!/usr/bin/env python3

import os
from typing import Tuple
import gradio as gr

from agentctl.config import settings
from agentctl.k8s_client import K8sClient
from agentctl.agent import K8sAgent

agent = K8sAgent()

def _client():
    return K8sClient()

def generate_yaml(prompt, namespace):
    if not prompt.strip():
        return "# Type something like: run python preprocess.py"
    return agent.nl_to_job_yaml(prompt, namespace)

def apply_yaml(yaml_text):
    if not yaml_text.strip():
        return "No YAML provided", ""
    c = _client()
    res = c.apply_manifest(yaml_text)
    return res.message, str(res.raw_response)

def snapshot():
    snap = _client().snapshot()
    out = [f"Namespace: {snap.namespace}", "", "Jobs:"]
    if not snap.jobs:
        out.append("  (none)")
    else:
        for j in snap.jobs:
            out.append(f"  - {j.name}: succeeded={j.succeeded}, failed={j.failed}, active={j.active}")

    out.append("")
    out.append("Pods:")
    if not snap.pods:
        out.append("  (none)")
    else:
        for p in snap.pods:
            out.append(f"  - {p.name}: {p.phase}")
    return "\n".join(out)

def logs(pod, tail):
    if not pod.strip():
        return "Enter pod name"
    return _client().get_pod_logs(pod, tail_lines=tail)

def build():
    with gr.Blocks(title="AgentCTL: K8s Automation") as ui:
        gr.Markdown("## AgentCTL — LLM-Driven Kubernetes Automation")

        with gr.Tab("Create Job"):
            prompt = gr.Textbox(lines=4, label="Describe job")
            ns = gr.Textbox(value=settings.k8s_namespace, label="Namespace")
            gen = gr.Button("Generate YAML")
            yaml_box = gr.Code(language="yaml", lines=20)
            apply = gr.Button("Apply to cluster")
            apply_msg = gr.Textbox(label="Status")
            apply_raw = gr.Textbox(label="Raw response")

            gen.click(generate_yaml, [prompt, ns], yaml_box)
            apply.click(apply_yaml, yaml_box, [apply_msg, apply_raw])

        with gr.Tab("Cluster Status"):
            btn = gr.Button("Refresh")
            box = gr.Textbox(lines=20)
            btn.click(snapshot, [], box)

        with gr.Tab("Pod Logs"):
            pod = gr.Textbox(label="Pod name")
            tail = gr.Slider(10, 500, step=10, value=100)
            btn2 = gr.Button("Get logs")
            out = gr.Textbox(lines=20)
            btn2.click(logs, [pod, tail], out)

    return ui

app = build()

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", 7860)))
