from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from uuid import uuid4
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.batch import router as batch_router
from app.api.phase3 import router as phase3_router
from app.services.batch import BatchInvestigationService
from app.services.phase3 import Phase3Service
from app.analysis.service import AnalysisService
from app.core.config import get_settings
from app.db.sqlite import SQLiteRepository
from app.evidence.service import EvidenceValidationService
from app.normalization.service import NormalizationService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    repository = SQLiteRepository(settings.database_url)
    repository.initialize()
    app.state.repository = repository
    app.state.evidence_validation_service = EvidenceValidationService(
        repository,
        max_file_size_bytes=settings.max_evidence_file_bytes,
        max_issues=settings.max_validation_issues,
    )
    app.state.normalization_service = NormalizationService()
    app.state.analysis_service = AnalysisService()
    app.state.batch_service = BatchInvestigationService(repository, settings.evidence_storage_path, settings.max_evidence_file_bytes, settings.max_validation_issues)
    app.state.phase3_service = Phase3Service(repository, app.state.batch_service, settings)
    yield
    app.state.phase3_service.shutdown()
    app.state.batch_service.shutdown()
    repository.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    @app.middleware("http")
    async def request_ids(request: Request, call_next):
        request_id=request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        try: response=await call_next(request)
        except KeyError as exc: response=JSONResponse(status_code=404,content={"code":str(exc.args[0]),"message":"Requested resource was not found.","retryable":False,"request_id":request_id,"details":None})
        except ValueError as exc: response=JSONResponse(status_code=409,content={"code":str(exc),"message":str(exc).replace("_"," "),"retryable":False,"request_id":request_id,"details":None})
        except PermissionError as exc: response=JSONResponse(status_code=401,content={"code":str(exc),"message":"Live source authentication failed.","retryable":False,"request_id":request_id,"details":None})
        except OverflowError as exc: response=JSONResponse(status_code=429 if "rate_limit" in str(exc) else 413,content={"code":str(exc),"message":str(exc).replace("_"," "),"retryable":"rate_limit" in str(exc),"request_id":request_id,"details":None})
        response.headers["x-request-id"]=request_id; return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request:Request, exc:RequestValidationError):
        request_id=request.headers.get("x-request-id") or str(uuid4())
        return JSONResponse(status_code=422,content={"code":"request_validation_error","message":"Request validation failed.","retryable":False,"request_id":request_id,"details":exc.errors()})
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(batch_router, prefix=settings.api_prefix)
    app.include_router(phase3_router, prefix=settings.api_prefix)
    return app


app = create_app()

