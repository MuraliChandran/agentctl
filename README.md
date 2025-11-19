---
title: AgentCTL – Kubernetes Agent UI
emoji: 🧠
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: "4.42.0"
app_file: app.py
pinned: false
---


# AgentCTL — LLM-Driven Kubernetes Automation  
### Natural Language → Kubernetes Jobs, Deployments & CronJobs  
Built for real clusters via Minikube + kubectl proxy + ngrok or Cloudflare Tunnel.

---

## 🚀 Overview

**AgentCTL** is an agentic workflow system that converts **natural language instructions** into **Kubernetes manifests** (Jobs, Deployments, CronJobs) and applies them to a **real Kubernetes cluster**.

It works by exposing your cluster via:

- `kubectl proxy`
- a public tunnel (`ngrok` or `cloudflared`)
- a Gradio web UI  
- a lightweight NL → YAML agent (heuristic + optional OpenAI LLM)

---

## ✨ Features

- Natural language → Kubernetes YAML  
- Supports:
  - Jobs
  - Deployments
  - CronJobs  
- Optional OpenAI LLM YAML refinement  
- Cluster dashboard (Jobs, Pods, Deployments, CronJobs)  
- Pod logs viewer  
- Pure HTTP client — no kubeconfig required  

---

## 🧱 Architecture

```
Gradio UI → AgentCTL (NL→YAML) → K8sClient (HTTP) → Kubernetes API
```

---

## 📦 Installation

```bash
pip install -r requirements.txt
```

or

```bash
conda create -n agentctl python=3.10 -y
conda activate agentctl
pip install -r requirements.txt
```

---

## 🧪 Minikube Setup

```bash
minikube start --driver=docker
kubectl get pods -A
```

Expose API publicly:

```bash
kubectl proxy   --port=8001   --address=0.0.0.0   --accept-hosts='.*'   --accept-paths='.*'
```

Tunnel:

```bash
ngrok http 8001
```

---

## 🌐 Environment Variables

```bash
export K8S_API_BASE_URL="https://xxxx.ngrok-free.dev"
export K8S_NAMESPACE="default"
export K8S_VERIFY_SSL=false
```

Enable LLM YAML:

```bash
export AGENTCTL_USE_LLM=true
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"
```

---

## ▶️ Run the App

```bash
python app.py
```

Open:

```
http://localhost:7860
```

---

## 📝 Usage Examples

### 🟦 Job
```
run a python job to preprocess data
```

### 🟧 Deployment
```
Prompt
create an nginx deployment with 3 replicas

Example
**Generated YAML:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
  labels:
    app: agentctl-deployment
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentctl-deployment
  template:
    metadata:
      labels:
        app: agentctl-deployment
    spec:
      containers:
        - name: main
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80

```

### 🟩 CronJob
```
Prompt
schedule a python cleanup script every 5 minutes

example
apiVersion: batch/v1
kind: CronJob
metadata:
  name: agentctl-cronjob
  namespace: default
spec:
  schedule: "*/5 * * * *"
  jobTemplate:
    spec:
      template:
        metadata:
          labels:
            app: agentctl-cronjob
        spec:
          restartPolicy: Never
          containers:
            - name: main
              image: python:3.11-slim
              command:
                - /bin/sh
                - -c
                - python cleanup.py

```

---

## 🚀 Deploy to Hugging Face Spaces

1. Create a Space (Gradio)
2. Upload project files
3. Set environment variables
4. Run the UI remotely controlling your real cluster

---

## 🔐 Security Notes

- ngrok + kubectl proxy is for demos only  
- For real environments use:
  - Cloudflare Tunnel  
  - RBAC service accounts  
  - Namespaced permissions  

---

## ❤️ Credits

Built by **Murali Chandran (codeninja3d)**  
AI Agents • Kubernetes • MLOps

---

## 📄 License

MIT License
