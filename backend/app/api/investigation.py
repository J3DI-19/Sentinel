from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request, Response, status

from app.analysis.schemas import (
    Alert,
    AnalysisResult,
    ChartPoint,
    DetectionFinding,
    GraphData,
    Incident,
    TimelineEntry,
)
from app.evidence.schemas import EvidenceSource, EvidenceValidationReport
from app.investigation.schemas import (
    AnalysisRunSummary,
    CaseCreate,
    CaseRecord,
    EvidenceIngestResponse,
    NormalizationFailure,
    ReanalysisRequest,
)
from app.normalization.schemas import CanonicalEvent, EventOrigin, NormalizationStatus


router = APIRouter(prefix="/cases", tags=["investigation"])
CaseId = Annotated[int, Path(ge=1)]


def _repository(request: Request):
    return request.app.state.repository


def _require_case(request: Request, case_id: int) -> CaseRecord:
    case = _repository(request).get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case


def _selected_analysis(
    request: Request, case_id: int, analysis_id: UUID | None
) -> AnalysisResult:
    _require_case(request, case_id)
    repository = _repository(request)
    result = (
        repository.get_analysis(case_id, analysis_id)
        if analysis_id is not None
        else repository.get_latest_analysis(case_id)
    )
    if result is None:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return result


@router.post("", response_model=CaseRecord, status_code=status.HTTP_201_CREATED)
async def create_case(payload: CaseCreate, request: Request) -> CaseRecord:
    return _repository(request).create_case(payload)


@router.get("", response_model=list[CaseRecord])
async def list_cases(request: Request) -> list[CaseRecord]:
    return _repository(request).list_cases()


@router.get("/{case_id}", response_model=CaseRecord)
async def get_case(case_id: CaseId, request: Request) -> CaseRecord:
    return _require_case(request, case_id)


@router.post(
    "/{case_id}/evidence",
    response_model=EvidenceIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_evidence(
    case_id: CaseId,
    request: Request,
    response: Response,
    filename: Annotated[str, Query(min_length=1, max_length=512)],
    source_type: EvidenceSource,
    content: Annotated[
        bytes,
        Body(
            media_type="application/octet-stream",
            description="Original CSV or JSON evidence bytes",
        ),
    ] = b"",
) -> EvidenceIngestResponse:
    _require_case(request, case_id)
    outcome = request.app.state.evidence_validation_service.validate_with_records(
        filename=filename,
        content=content,
        source_type=source_type,
        case_id=case_id,
        media_type=request.headers.get("content-type"),
    )
    events: list[CanonicalEvent] = []
    failures: list[NormalizationFailure] = []
    for record in outcome.accepted_records:
        normalized = request.app.state.normalization_service.normalize_batch_record(
            metadata=outcome.report.metadata,
            validated_record=record,
        )
        if normalized.status == NormalizationStatus.NORMALIZED:
            if normalized.event is None:
                raise RuntimeError("normalized result did not contain an event")
            events.append(normalized.event)
        else:
            failures.append(
                NormalizationFailure(
                    source_record_reference=normalized.source_record_reference,
                    issues=normalized.issues,
                )
            )
    _repository(request).store_canonical_events(events)
    if outcome.report.status.value == "rejected":
        response.status_code = status.HTTP_200_OK
    return EvidenceIngestResponse(
        validation=outcome.report,
        normalized_event_count=len(events),
        events=events,
        normalization_failures=failures,
    )


@router.get("/{case_id}/evidence", response_model=list[EvidenceValidationReport])
async def list_evidence(
    case_id: CaseId, request: Request
) -> list[EvidenceValidationReport]:
    _require_case(request, case_id)
    return _repository(request).list_evidence(case_id)


@router.get(
    "/{case_id}/evidence/{evidence_id}", response_model=EvidenceValidationReport
)
async def get_evidence(
    case_id: CaseId, evidence_id: UUID, request: Request
) -> EvidenceValidationReport:
    _require_case(request, case_id)
    report = _repository(request).get_evidence(case_id, evidence_id)
    if report is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    return report


@router.get("/{case_id}/events", response_model=list[CanonicalEvent])
async def list_events(
    case_id: CaseId,
    request: Request,
    event_type: Annotated[list[str] | None, Query()] = None,
    origin: Annotated[list[EventOrigin] | None, Query()] = None,
    evidence_id: UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[CanonicalEvent]:
    _require_case(request, case_id)
    events = _repository(request).list_canonical_events(case_id)
    if event_type:
        selected_types = set(event_type)
        events = [event for event in events if event.event_type in selected_types]
    if origin:
        selected_origins = set(origin)
        events = [
            event for event in events if event.provenance.origin in selected_origins
        ]
    if evidence_id is not None:
        events = [
            event
            for event in events
            if event.provenance.evidence_id == evidence_id
        ]
    return events[offset : offset + limit]


@router.get("/{case_id}/events/{event_id}", response_model=CanonicalEvent)
async def get_event(
    case_id: CaseId, event_id: UUID, request: Request
) -> CanonicalEvent:
    _require_case(request, case_id)
    event = _repository(request).get_canonical_event(case_id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return event


@router.post("/{case_id}/analysis/reanalyze", response_model=AnalysisResult)
async def reanalyze_case(
    case_id: CaseId, payload: ReanalysisRequest, request: Request
) -> AnalysisResult:
    _require_case(request, case_id)
    events = _repository(request).list_canonical_events(case_id)
    result = request.app.state.analysis_service.analyze(
        case_id=case_id,
        events=events,
        event_filter=payload.filter,
    )
    _repository(request).store_analysis(result)
    return result


@router.get("/{case_id}/analysis", response_model=AnalysisResult)
async def refresh_analysis(case_id: CaseId, request: Request) -> AnalysisResult:
    return _selected_analysis(request, case_id, None)


@router.get("/{case_id}/analysis/runs", response_model=list[AnalysisRunSummary])
async def list_analysis_runs(
    case_id: CaseId, request: Request
) -> list[AnalysisRunSummary]:
    _require_case(request, case_id)
    return _repository(request).list_analysis_runs(case_id)


@router.get("/{case_id}/analysis/runs/{analysis_id}", response_model=AnalysisResult)
async def get_analysis_run(
    case_id: CaseId, analysis_id: UUID, request: Request
) -> AnalysisResult:
    return _selected_analysis(request, case_id, analysis_id)


@router.get("/{case_id}/findings", response_model=list[DetectionFinding])
async def list_findings(
    case_id: CaseId, request: Request, analysis_id: UUID | None = None
) -> list[DetectionFinding]:
    return _selected_analysis(request, case_id, analysis_id).findings


@router.get("/{case_id}/findings/{finding_id}", response_model=DetectionFinding)
async def get_finding(
    case_id: CaseId,
    finding_id: UUID,
    request: Request,
    analysis_id: UUID | None = None,
) -> DetectionFinding:
    result = _selected_analysis(request, case_id, analysis_id)
    finding = next(
        (item for item in result.findings if item.finding_id == finding_id), None
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    return finding


@router.get("/{case_id}/alerts", response_model=list[Alert])
async def list_alerts(
    case_id: CaseId, request: Request, analysis_id: UUID | None = None
) -> list[Alert]:
    return _selected_analysis(request, case_id, analysis_id).alerts


@router.get("/{case_id}/alerts/{alert_id}", response_model=Alert)
async def get_alert(
    case_id: CaseId,
    alert_id: UUID,
    request: Request,
    analysis_id: UUID | None = None,
) -> Alert:
    result = _selected_analysis(request, case_id, analysis_id)
    alert = next((item for item in result.alerts if item.alert_id == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert


@router.get("/{case_id}/incidents", response_model=list[Incident])
async def list_incidents(
    case_id: CaseId, request: Request, analysis_id: UUID | None = None
) -> list[Incident]:
    return _selected_analysis(request, case_id, analysis_id).incidents


@router.get("/{case_id}/incidents/{incident_id}", response_model=Incident)
async def get_incident(
    case_id: CaseId,
    incident_id: UUID,
    request: Request,
    analysis_id: UUID | None = None,
) -> Incident:
    result = _selected_analysis(request, case_id, analysis_id)
    incident = next(
        (item for item in result.incidents if item.incident_id == incident_id), None
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@router.get("/{case_id}/timeline", response_model=list[TimelineEntry])
async def get_timeline(
    case_id: CaseId, request: Request, analysis_id: UUID | None = None
) -> list[TimelineEntry]:
    return _selected_analysis(request, case_id, analysis_id).timeline


@router.get("/{case_id}/graph", response_model=GraphData)
async def get_graph(
    case_id: CaseId, request: Request, analysis_id: UUID | None = None
) -> GraphData:
    return _selected_analysis(request, case_id, analysis_id).graph


@router.get("/{case_id}/charts", response_model=list[ChartPoint])
async def get_charts(
    case_id: CaseId, request: Request, analysis_id: UUID | None = None
) -> list[ChartPoint]:
    return _selected_analysis(request, case_id, analysis_id).chart_points
