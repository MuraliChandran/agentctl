# AgentCTL: LLM-Driven Kubernetes Automation

AgentCTL connects a natural-language interface to a **real Kubernetes cluster**.

You describe the job you want to run; AgentCTL generates a Kubernetes
Job manifest and applies it to your cluster via the Kubernetes API
server (e.g. Minikube exposed with `kubectl proxy` + ngrok).

---

## Quickstart

### 1. Start Minikube

```bash
minikube start --driver=docker
kubectl get nodes
