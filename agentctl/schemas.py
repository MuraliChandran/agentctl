from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ApplyResult(BaseModel):
    success: bool
    message: str
    raw_response: Optional[Dict[str, Any]] = None


class JobStatus(BaseModel):
    name: str
    namespace: str
    succeeded: int = 0
    failed: int = 0
    active: int = 0


class PodInfo(BaseModel):
    name: str
    phase: str
    node_name: Optional[str] = None


class DeploymentStatus(BaseModel):
    name: str
    namespace: str
    replicas: int = 0
    ready: int = 0


class CronJobStatus(BaseModel):
    name: str
    namespace: str
    active: int = 0
    last_schedule: Optional[str] = None


class ClusterSnapshot(BaseModel):
    namespace: str
    jobs: List[JobStatus] = Field(default_factory=list)
    pods: List[PodInfo] = Field(default_factory=list)
    deployments: List[DeploymentStatus] = Field(default_factory=list)
    cronjobs: List[CronJobStatus] = Field(default_factory=list)
