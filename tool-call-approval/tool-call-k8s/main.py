import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import k8s_service
from logging_config import reconfigure_uvicorn_loggers, setup_logging
from models import AgentResponse, DeployRequest, KubeconfigRequest, ScaleRequest

setup_logging("tool-call-k8s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    reconfigure_uvicorn_loggers("tool-call-k8s")
    yield


app = FastAPI(title="K8s Manager", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/kubeconfig")
async def save_kubeconfig(request: KubeconfigRequest) -> dict:
    try:
        k8s_service.write_kubeconfig(request.content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "ok"}


@app.post("/agents", response_model=AgentResponse, status_code=201)
async def create_agent(request: DeployRequest) -> AgentResponse:
    try:
        result = k8s_service.create_deployment(
            name=request.name,
            image=request.image,
            namespace=request.namespace,
            replicas=request.replicas,
            env=[e.model_dump() for e in request.env],
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "already exists" in msg:
            raise HTTPException(status_code=400, detail=msg)
        if "kubeconfig not configured" in msg:
            raise HTTPException(status_code=503, detail="kubeconfig not configured")
        raise HTTPException(status_code=500, detail=msg)
    return AgentResponse(**result)


@app.get("/agents", response_model=list[AgentResponse])
async def list_agents() -> list[AgentResponse]:
    try:
        items = k8s_service.list_deployments()
    except RuntimeError as exc:
        msg = str(exc)
        if "kubeconfig not configured" in msg:
            raise HTTPException(status_code=503, detail="kubeconfig not configured")
        raise HTTPException(status_code=500, detail=msg)
    return [AgentResponse(**item) for item in items]


@app.delete("/agents/{name}")
async def delete_agent(name: str, namespace: str = "default") -> dict:
    try:
        k8s_service.delete_deployment(name, namespace)
    except RuntimeError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=f"Deployment {name} not found")
        raise HTTPException(status_code=500, detail=msg)
    return {"status": "ok"}


@app.post("/agents/{name}/restart")
async def restart_agent(name: str, namespace: str = "default") -> dict:
    try:
        k8s_service.restart_deployment(name, namespace)
    except RuntimeError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=f"Deployment {name} not found")
        raise HTTPException(status_code=500, detail=msg)
    return {"status": "ok"}


@app.patch("/agents/{name}/scale")
async def scale_agent(name: str, request: ScaleRequest, namespace: str = "default") -> dict:
    try:
        k8s_service.scale_deployment(name, namespace, request.replicas)
    except RuntimeError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=f"Deployment {name} not found")
        raise HTTPException(status_code=500, detail=msg)
    return {"status": "ok"}
