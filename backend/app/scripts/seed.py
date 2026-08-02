import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db import SessionFactory
from app.models import Tenant, User, Workspace, WorkspaceMember


async def seed() -> None:
    settings = get_settings()
    async with SessionFactory() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.code == "default"))
        if not tenant:
            tenant = Tenant(name="Default Tenant", code="default", status="active")
            session.add(tenant)
            await session.flush()
        user = await session.scalar(
            select(User).where(
                User.tenant_id == tenant.id,
                User.username == settings.initial_admin_username,
            )
        )
        if not user:
            user = User(
                tenant_id=tenant.id,
                username=settings.initial_admin_username,
                email=settings.initial_admin_email,
                password_hash=hash_password(settings.initial_admin_password),
                display_name="Administrator",
                status="active",
                is_tenant_admin=True,
            )
            session.add(user)
            await session.flush()
        workspace = await session.scalar(
            select(Workspace).where(
                Workspace.tenant_id == tenant.id,
                Workspace.name == "Default Workspace",
            )
        )
        if not workspace:
            workspace = Workspace(
                tenant_id=tenant.id,
                name="Default Workspace",
                description="默认工作空间",
                status="active",
                created_by=user.id,
            )
            session.add(workspace)
            await session.flush()
            session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        await session.commit()
        print(f"Seed complete: {settings.initial_admin_username}")


if __name__ == "__main__":
    asyncio.run(seed())
