from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import yaml_gen, apply, snapshot, logs

app = FastAPI(
    title="AgentCTL Backend API",
    version="1.0.0",
    description="Backend API for Kubernetes AgentCTL automation",
)

# CORS (UI → API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(yaml_gen.router)
app.include_router(apply.router)
app.include_router(snapshot.router)
app.include_router(logs.router)


@app.get("/")
def root():
    return {"status": "AgentCTL Backend Running"}
