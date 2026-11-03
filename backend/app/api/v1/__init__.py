"""Agregação das rotas versionadas da API."""

from fastapi import APIRouter

from app.api.v1 import agent, auth, servers, system

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(servers.router)
api_router.include_router(agent.router)
api_router.include_router(system.router)

__all__ = ["api_router"]
