from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Job, Organization
from app.schemas.organization import OrganizationCreate, OrganizationOut, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _to_out(db: Session, org: Organization) -> OrganizationOut:
    job_count = db.execute(
        select(func.count()).select_from(Job).where(Job.organization_id == org.id)
    ).scalar_one()
    return OrganizationOut(
        id=org.id,
        name=org.name,
        organization_type=org.organization_type,
        province=org.province,
        city=org.city,
        official_url=org.official_url,
        career_url=org.career_url,
        notes=org.notes,
        job_count=job_count,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


def _get_org_or_404(db: Session, org_id: int) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail=f"单位不存在: {org_id}")
    return org


@router.get("", response_model=list[OrganizationOut])
def list_organizations(
    q: str | None = Query(None, description="按名称搜索"),
    db: Session = Depends(get_db),
):
    stmt = select(Organization).order_by(Organization.name)
    if q:
        stmt = stmt.where(Organization.name.ilike(f"%{q}%"))
    return [_to_out(db, org) for org in db.scalars(stmt)]


@router.post("", response_model=OrganizationOut, status_code=201)
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    org = Organization(**payload.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return _to_out(db, org)


@router.get("/{org_id}", response_model=OrganizationOut)
def get_organization(org_id: int, db: Session = Depends(get_db)):
    return _to_out(db, _get_org_or_404(db, org_id))


@router.patch("/{org_id}", response_model=OrganizationOut)
def update_organization(
    org_id: int, payload: OrganizationUpdate, db: Session = Depends(get_db)
):
    org = _get_org_or_404(db, org_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return _to_out(db, org)


@router.delete("/{org_id}", status_code=204)
def delete_organization(org_id: int, db: Session = Depends(get_db)):
    org = _get_org_or_404(db, org_id)
    in_use = db.execute(
        select(func.count()).select_from(Job).where(Job.organization_id == org_id)
    ).scalar_one()
    if in_use:
        raise HTTPException(status_code=409, detail=f"该单位下仍有 {in_use} 个岗位，无法删除")
    db.delete(org)
    db.commit()
