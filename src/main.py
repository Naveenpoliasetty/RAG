from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import parser_resume, get_unique_job_roles
from src.core.config import settings

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

# Include routerss 
# This is for redeployment testing 123

app.include_router(get_unique_job_roles.router, prefix="/api/v1", tags=["Get Unique Job Roles"])
app.include_router(parser_resume.router, prefix="/api/v1", tags=["Parser Resume"])

@app.get("/")
async def root():
    return {"message": "Resume API Service"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Resume API"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Resume API"}


#Lets Test it 