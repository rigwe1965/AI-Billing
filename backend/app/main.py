from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import allocations, auth, budgets, connectors, costs, departments, insights, pricing, providers, reports, usage, users
from app.core.config import settings
from app.jobs.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Both hostnames are needed: browsers treat localhost and 127.0.0.1 as
    # distinct origins even though they resolve to the same machine, and a
    # cookie-based session (allow_credentials) requires an exact origin match.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(providers.router)
app.include_router(departments.router)
app.include_router(pricing.router)
app.include_router(usage.router)
app.include_router(costs.router)
app.include_router(allocations.router)
app.include_router(connectors.router)
app.include_router(budgets.router)
app.include_router(reports.router)
app.include_router(insights.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
