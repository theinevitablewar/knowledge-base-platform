from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import PrincipalDep, SessionDep
from app.models import AuditLog
from app.schemas.common import AuditOut

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=list[AuditOut])
async def audit_logs(session: SessionDep, principal: PrincipalDep) -> list[AuditLog]:
    return list(
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.tenant_id == principal.tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(500)
        )
    )
