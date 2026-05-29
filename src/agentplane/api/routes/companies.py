"""Company CRUD routes."""

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from agentplane.core.db import get_async_session
from agentplane.core.models import Company

router = APIRouter()


@router.post("", response_model=Company)
async def create_company(company: Company):
    async with get_async_session() as session:
        session.add(company)
        await session.commit()
        await session.refresh(company)
        return company


@router.get("", response_model=list[Company])
async def list_companies():
    async with get_async_session() as session:
        result = await session.execute(select(Company))
        return list(result.scalars().all())


@router.get("/{company_id}", response_model=Company)
async def get_company(company_id: str):
    async with get_async_session() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return company


@router.delete("/{company_id}")
async def delete_company(company_id: str):
    async with get_async_session() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        await session.delete(company)
        await session.commit()
        return {"deleted": True}
