from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.evidence.schemas import EvidenceSource

router=APIRouter(tags=["batch-investigation"])

class CaseCreate(BaseModel):
    name:str=Field(min_length=1,max_length=200); description:str=Field(default="",max_length=2000); owner:str=Field(default="Investigator",max_length=120)
class CommitRequest(BaseModel): allow_partial:bool=False
class CasePublic(BaseModel):
    id:int; name:str; description:str; case_type:str; status:str; owner:str; created_at:str; updated_at:str|None=None
class PageResponse(BaseModel):
    items:list[dict[str,Any]]; page:int; page_size:int; total:int
class ImportPublic(BaseModel):
    import_id:str; case_id:int; evidence_id:str|None; filename:str; source_type:str; state:str
    progress:dict[str,Any]; validation:dict[str,Any]|None; error:dict[str,Any]|None; created_at:str; updated_at:str
class ErrorPublic(BaseModel):
    code:str; message:str; retryable:bool; request_id:str; details:Any|None=None

def service(request:Request): return request.app.state.batch_service
def page(items:list[dict], total:int, page_number:int, page_size:int): return {"items":items,"page":page_number,"page_size":page_size,"total":total}
def public_import(job:dict)->dict:
    return {"import_id":job["import_id"],"case_id":job["case_id"],"evidence_id":job["evidence_id"],"filename":job["filename"],"source_type":job["source_type"],"state":job["status"],"progress":{"mode":"indeterminate"},"validation":json.loads(job["validation_json"]) if job["validation_json"] else None,"error":json.loads(job["error_json"]) if job["error_json"] else None,"created_at":job["created_at"],"updated_at":job["updated_at"]}

@router.post("/cases",status_code=201)
def create_case(body:CaseCreate,request:Request) -> CasePublic: return service(request).create_case(body.name,body.description,body.owner)

@router.get("/cases")
def cases(request:Request,page_number:int=Query(1,alias="page",ge=1),page_size:int=Query(25,ge=1,le=100)) -> PageResponse:
    db=service(request).db; total=db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    rows=[dict(r) for r in db.execute("SELECT * FROM cases ORDER BY COALESCE(updated_at,created_at) DESC,id DESC LIMIT ? OFFSET ?",(page_size,(page_number-1)*page_size)).fetchall()]
    return page(rows,total,page_number,page_size)

@router.get("/cases/{case_id}")
def case(case_id:int,request:Request) -> CasePublic: return service(request).get_case(case_id)

@router.get("/cases/{case_id}/summary")
def case_summary(case_id:int,request:Request):
    svc=service(request); case=svc.get_case(case_id); db=svc.db
    events=db.execute("SELECT COUNT(*),COUNT(DISTINCT entity_id) FROM canonical_events WHERE case_id=?",(case_id,)).fetchone()
    latest=db.execute("SELECT analysis_id FROM analysis_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 1",(case_id,)).fetchone()
    counts={k:0 for k in ("finding","alert","incident")}; maximum=0
    if latest:
        for kind in counts: counts[kind]=db.execute("SELECT COUNT(*) FROM analysis_artifacts WHERE analysis_id=? AND kind=?",(latest[0],kind)).fetchone()[0]
        maximum=db.execute("SELECT COALESCE(MAX(risk),0) FROM analysis_artifacts WHERE analysis_id=?",(latest[0],)).fetchone()[0]
    return {"case":case,"event_count":events[0],"entity_count":events[1],"finding_count":counts["finding"],"alert_count":counts["alert"],"incident_count":counts["incident"],"maximum_risk":maximum,"analysis_id":latest[0] if latest else None}

@router.post("/cases/{case_id}/imports",status_code=202)
async def upload_import(case_id:int,request:Request,file:UploadFile=File(...),source_type:EvidenceSource=Form(...),timezone:str=Form("UTC"),timestamp_field:str=Form("auto"),duplicate_policy:str=Form("skip_exact_hashes"),label:str=Form("")) -> ImportPublic:
    content=await file.read(); config={"timezone":timezone,"timestamp_field":timestamp_field,"duplicate_policy":duplicate_policy,"label":label}
    return public_import(service(request).start_import(case_id,file.filename or "evidence",content,source_type,config,file.content_type))

@router.get("/imports/{import_id}")
def import_status(import_id:UUID,request:Request) -> ImportPublic: return public_import(service(request).get_import(str(import_id)))
@router.post("/imports/{import_id}/commit",status_code=202)
def commit(import_id:UUID,body:CommitRequest,request:Request) -> ImportPublic: return public_import(service(request).request_commit(str(import_id),body.allow_partial))
@router.post("/imports/{import_id}/cancel")
def cancel(import_id:UUID,request:Request) -> ImportPublic: return public_import(service(request).cancel(str(import_id)))

@router.get("/cases/{case_id}/evidence")
def evidence(case_id:int,request:Request,page_number:int=Query(1,alias="page",ge=1),page_size:int=Query(25,ge=1,le=100),source:EvidenceSource|None=None) -> PageResponse:
    service(request).get_case(case_id); db=service(request).db; where="case_id=?"; values:list[Any]=[case_id]
    if source: where += " AND source_type=?"; values.append(source.value)
    total=db.execute(f"SELECT COUNT(*) FROM evidence_metadata WHERE {where}",values).fetchone()[0]
    rows=[dict(r) for r in db.execute(f"SELECT * FROM evidence_metadata WHERE {where} ORDER BY received_at DESC,id DESC LIMIT ? OFFSET ?",(*values,page_size,(page_number-1)*page_size)).fetchall()]
    return page(rows,total,page_number,page_size)
@router.get("/evidence/{evidence_id}")
def evidence_detail(evidence_id:UUID,request:Request):
    db=service(request).db; row=db.execute("SELECT * FROM evidence_metadata WHERE evidence_id=?",(str(evidence_id),)).fetchone()
    if not row: raise KeyError("evidence_not_found")
    result=dict(row); result["issues"]=[dict(r) for r in db.execute("SELECT level,error_code,message,row_number,field_name,rejected_value FROM evidence_validation_issues WHERE evidence_metadata_id=?",(row["id"],)).fetchall()]; return result

@router.get("/cases/{case_id}/evidence/{evidence_id}")
def case_evidence_detail(case_id:int,evidence_id:UUID,request:Request):
    service(request).get_case(case_id); db=service(request).db
    row=db.execute("SELECT * FROM evidence_metadata WHERE case_id=? AND evidence_id=?",(case_id,str(evidence_id))).fetchone()
    if not row: raise KeyError("evidence_not_found")
    result=dict(row); result["issues"]=[dict(r) for r in db.execute("SELECT level,error_code,message,row_number,field_name,rejected_value FROM evidence_validation_issues WHERE evidence_metadata_id=?",(row["id"],)).fetchall()]; return result

@router.get("/cases/{case_id}/events")
def events(case_id:int,request:Request,page_number:int=Query(1,alias="page",ge=1),page_size:int=Query(50,ge=1,le=200),origin:str|None=None,event_type:str|None=None,entity:str|None=None,source:EvidenceSource|None=None,start_time:str|None=None,end_time:str|None=None) -> PageResponse:
    service(request).get_case(case_id); db=service(request).db; where=["case_id=?"]; values:list[Any]=[case_id]
    if origin: where.append("origin=?"); values.append(origin)
    if event_type: where.append("event_type=?"); values.append(event_type)
    if entity: where.append("entity_id=?"); values.append(entity)
    if source: where.append("evidence_id IN (SELECT evidence_id FROM evidence_metadata WHERE case_id=? AND source_type=?)"); values.extend([case_id,source.value])
    if start_time: where.append("COALESCE(observed_at,ingested_at)>=?"); values.append(start_time)
    if end_time: where.append("COALESCE(observed_at,ingested_at)<=?"); values.append(end_time)
    clause=" AND ".join(where); total=db.execute(f"SELECT COUNT(*) FROM canonical_events WHERE {clause}",values).fetchone()[0]
    rows=db.execute(f"SELECT canonical_json,raw_record_json FROM canonical_events WHERE {clause} ORDER BY COALESCE(observed_at,ingested_at),event_id LIMIT ? OFFSET ?",(*values,page_size,(page_number-1)*page_size)).fetchall()
    return page([{**json.loads(r[0]),"raw_record":json.loads(r[1])} for r in rows],total,page_number,page_size)
@router.get("/events/{event_id}")
def event(event_id:UUID,request:Request):
    row=service(request).db.execute("SELECT canonical_json,raw_record_json FROM canonical_events WHERE event_id=?",(str(event_id),)).fetchone()
    if not row: raise KeyError("event_not_found")
    return {**json.loads(row[0]),"raw_record":json.loads(row[1])}

@router.get("/cases/{case_id}/events/{event_id}")
def case_event(case_id:int,event_id:UUID,request:Request):
    service(request).get_case(case_id)
    row=service(request).db.execute("SELECT canonical_json,raw_record_json FROM canonical_events WHERE case_id=? AND event_id=?",(case_id,str(event_id))).fetchone()
    if not row: raise KeyError("event_not_found")
    return {**json.loads(row[0]),"raw_record":json.loads(row[1])}

def artifacts(case_id:int,kind:str,request:Request,page_number:int,page_size:int,severity:str|None=None,start_time:str|None=None,end_time:str|None=None,analysis_id:UUID|None=None):
    service(request).get_case(case_id); db=service(request).db
    latest=(db.execute("SELECT analysis_id FROM analysis_runs WHERE case_id=? AND analysis_id=?",(case_id,str(analysis_id))).fetchone() if analysis_id else db.execute("SELECT analysis_id FROM analysis_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 1",(case_id,)).fetchone())
    if not latest:return page([],0,page_number,page_size)
    where=["analysis_id=?","kind=?"]; values:list[Any]=[latest[0],kind]
    if severity: where.append("severity=?"); values.append(severity)
    if start_time: where.append("occurred_at>=?"); values.append(start_time)
    if end_time: where.append("occurred_at<=?"); values.append(end_time)
    clause=" AND ".join(where); total=db.execute(f"SELECT COUNT(*) FROM analysis_artifacts WHERE {clause}",values).fetchone()[0]
    rows=db.execute(f"SELECT payload_json FROM analysis_artifacts WHERE {clause} ORDER BY COALESCE(occurred_at,''),item_id LIMIT ? OFFSET ?",(*values,page_size,(page_number-1)*page_size)).fetchall()
    return page([json.loads(r[0]) for r in rows],total,page_number,page_size)

@router.post("/cases/{case_id}/analyses",status_code=202)
def reanalyze(case_id:int,request:Request): return service(request).reanalyze(case_id)

@router.get("/cases/{case_id}/analyses")
def analyses(case_id:int,request:Request,page_number:int=Query(1,alias="page",ge=1),page_size:int=Query(25,ge=1,le=100)) -> PageResponse:
    service(request).get_case(case_id); db=service(request).db
    total=db.execute("SELECT COUNT(*) FROM analysis_runs WHERE case_id=?",(case_id,)).fetchone()[0]
    rows=[dict(r) for r in db.execute("SELECT analysis_id,case_id,status,created_at FROM analysis_runs WHERE case_id=? ORDER BY created_at DESC,analysis_id DESC LIMIT ? OFFSET ?",(case_id,page_size,(page_number-1)*page_size)).fetchall()]
    return page(rows,total,page_number,page_size)

@router.get("/cases/{case_id}/analyses/latest")
def latest_analysis(case_id:int,request:Request):
    service(request).get_case(case_id); row=service(request).db.execute("SELECT result_json FROM analysis_runs WHERE case_id=? ORDER BY created_at DESC,analysis_id DESC LIMIT 1",(case_id,)).fetchone()
    if not row: raise KeyError("analysis_not_found")
    return json.loads(row[0])

@router.get("/cases/{case_id}/analyses/{analysis_id}")
def case_analysis(case_id:int,analysis_id:UUID,request:Request):
    service(request).get_case(case_id); row=service(request).db.execute("SELECT result_json FROM analysis_runs WHERE case_id=? AND analysis_id=?",(case_id,str(analysis_id))).fetchone()
    if not row: raise KeyError("analysis_not_found")
    return json.loads(row[0])
@router.get("/analyses/{analysis_id}")
def analysis(analysis_id:UUID,request:Request):
    row=service(request).db.execute("SELECT result_json FROM analysis_runs WHERE analysis_id=?",(str(analysis_id),)).fetchone()
    if not row:raise KeyError("analysis_not_found")
    return json.loads(row[0])

def artifact_endpoint(kind: str):
    def endpoint(case_id:int,request:Request,page_number:int=Query(1,alias="page",ge=1),page_size:int=Query(50,ge=1,le=200),severity:str|None=None,start_time:str|None=None,end_time:str|None=None,analysis_id:UUID|None=None):
        return artifacts(case_id,kind,request,page_number,page_size,severity,start_time,end_time,analysis_id)
    return endpoint

for path,kind in [("findings","finding"),("alerts","alert"),("incidents","incident"),("timeline","timeline")]:
    router.add_api_route(f"/cases/{{case_id}}/{path}",artifact_endpoint(kind),methods=["GET"],name=f"list_{path}")

@router.get("/cases/{case_id}/graph")
def graph(case_id:int,request:Request,node_limit:int=Query(500,ge=1,le=1000),edge_limit:int=Query(1000,ge=1,le=2000),analysis_id:UUID|None=None):
    nodes=artifacts(case_id,"graph_node",request,1,node_limit,analysis_id=analysis_id); edges=artifacts(case_id,"graph_edge",request,1,edge_limit,analysis_id=analysis_id)
    return {"nodes":nodes["items"],"edges":edges["items"],"truncated":nodes["total"]>node_limit or edges["total"]>edge_limit}
@router.get("/cases/{case_id}/aggregates")
def aggregates(case_id:int,request:Request,analysis_id:UUID|None=None): return artifacts(case_id,"aggregate",request,1,200,analysis_id=analysis_id)
@router.get("/cases/{case_id}/charts")
def charts(case_id:int,request:Request,analysis_id:UUID|None=None): return artifacts(case_id,"aggregate",request,1,200,analysis_id=analysis_id)
@router.get("/dashboard/summary")
def dashboard(request:Request):
    db=service(request).db
    return {"case_count":db.execute("SELECT COUNT(*) FROM cases").fetchone()[0],"event_count":db.execute("SELECT COUNT(*) FROM canonical_events").fetchone()[0],"active_cases":db.execute("SELECT COUNT(*) FROM cases WHERE status='active'").fetchone()[0],"recent_cases":[dict(r) for r in db.execute("SELECT * FROM cases ORDER BY COALESCE(updated_at,created_at) DESC LIMIT 5").fetchall()]}
