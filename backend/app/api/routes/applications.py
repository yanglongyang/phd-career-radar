"""Application CRM API（Phase 5）。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.application import (
    ApplicationCreate,
    ApplicationListPage,
    ApplicationOut,
    ApplicationUpdate,
)
from app.services import applications as application_service

router = APIRouter(tags=["applications"])


@router.get("/applications", response_model=ApplicationListPage)
def list_applications(
    status: str | None = Query(None, description="按状态过滤"),
    q: str | None = Query(None, description="搜索 next_action/备注/联系人"),
    sort: str = Query("updated_at", description="updated_at | next_action_date | priority"),
    db: Session = Depends(get_db),
):
    items = application_service.list_applications(db, status=status, q=q, sort=sort)
    return ApplicationListPage(
        items=[application_service.to_out(db, app) for app in items],
        total=len(items),
    )


@router.post("/jobs/{job_id}/application", response_model=ApplicationOut, status_code=201)
def create_application(job_id: int, payload: ApplicationCreate, db: Session = Depends(get_db)):
    try:
        app = application_service.create_application(db, job_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except application_service.ApplicationExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    db.refresh(app)
    return application_service.to_out(db, app)


@router.get("/jobs/{job_id}/application", response_model=ApplicationOut | None)
def get_application_by_job(job_id: int, db: Session = Depends(get_db)):
    app = application_service.get_application_by_job(db, job_id)
    return application_service.to_out(db, app) if app else None


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)
):
    try:
        app = application_service.get_application_or_404(db, application_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        app = application_service.update_application(db, app, payload)
    except application_service.ApplicationTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    db.refresh(app)
    return application_service.to_out(db, app)


@router.delete("/applications/{application_id}", status_code=204)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    try:
        app = application_service.get_application_or_404(db, application_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    application_service.delete_application(db, app)  # 岗位与评估结果保留
    db.commit()
