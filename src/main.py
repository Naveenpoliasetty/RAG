import os
# Suppress Hugging Face tokenizers parallelism warning
# Set this before any tokenizers are imported
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import parser_resume, get_unique_job_roles, generate_resume
from src.core.config import settings
from src.core.db_manager import initialize_connections, close_connections


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize database connections on startup."""
    await initialize_connections()


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    close_connections()


# Include routerss      

app.include_router(get_unique_job_roles.router, prefix="/api/v1", tags=["Get Unique Job Roles"])
app.include_router(parser_resume.router, prefix="/api/v1", tags=["Parser Resume"])
app.include_router(generate_resume.router, prefix="/api/v1", tags=["Resume Generator"])

@app.get("/")
async def root():
    return {"message": "Resume API Service"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Resume API"}

