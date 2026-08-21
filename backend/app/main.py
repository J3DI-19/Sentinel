from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.investigation import router as investigation_router
from app.analysis.service import AnalysisService
from app.core.config import get_settings
from app.db.sqlite import SQLiteRepository
from app.evidence.authorization import ValidationAuthority
from app.evidence.service import EvidenceValidationService, LiveTelemetryAcceptanceService
from app.normalization.service import NormalizationService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    repository = SQLiteRepository(settings.database_url)
    repository.initialize()
    app.state.repository = repository
    validation_authority = ValidationAuthority()
    app.state.evidence_validation_service = EvidenceValidationService(
        repository,
        validation_authority=validation_authority,
        max_file_size_bytes=settings.max_evidence_file_bytes,
        max_issues=settings.max_validation_issues,
    )
    app.state.live_telemetry_acceptance_service = LiveTelemetryAcceptanceService()
    app.state.normalization_service = NormalizationService(validation_authority)
    app.state.analysis_service = AnalysisService()
    yield
    repository.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(investigation_router, prefix=settings.api_prefix)
    return app


app = create_app()

