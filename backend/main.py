from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import yaml_gen, apply, snapshot, logs, agent

app = FastAPI(
    title="AgentCTL Backend API",
    version="1.0.0",
    description="Backend API for Kubernetes AgentCTL automation",
)

# CORS (for Gradio UI, HF Space, other tools)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Status"])
def root():
    """Simple health endpoint."""
    return {"status": "AgentCTL Backend Running"}


# Attach routers under /api/*
app.include_router(yaml_gen.router, prefix="/api")
app.include_router(apply.router, prefix="/api")
app.include_router(snapshot.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(agent.router, prefix="/api") 

@app.get("/debug-env")
def debug_env():
    import os
    return {
        "K8S_API_BASE_URL": os.getenv("K8S_API_BASE_URL"),
        "K8S_NAMESPACE": os.getenv("K8S_NAMESPACE"),
        "K8S_VERIFY_SSL": os.getenv("K8S_VERIFY_SSL")
    }
