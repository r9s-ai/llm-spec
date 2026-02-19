"""Provider config APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_spec.web.db import get_db
from llm_spec.web.models import ProviderConfigModel
from llm_spec.web.schemas import ProviderConfigResponse, ProviderConfigUpsertRequest

router = APIRouter(prefix="/api/provider-configs", tags=["provider-configs"])


@router.get("", response_model=list[ProviderConfigResponse])
def list_provider_configs(db: Session = Depends(get_db)) -> list[ProviderConfigModel]:
    stmt = select(ProviderConfigModel).order_by(ProviderConfigModel.provider.asc())
    return list(db.execute(stmt).scalars().all())


@router.get("/{provider}", response_model=ProviderConfigResponse)
def get_provider_config(provider: str, db: Session = Depends(get_db)) -> ProviderConfigModel:
    row = db.get(ProviderConfigModel, provider)
    if row is None:
        raise HTTPException(status_code=404, detail="provider config not found")
    return row


@router.put("/{provider}", response_model=ProviderConfigResponse)
def upsert_provider_config(
    provider: str,
    payload: ProviderConfigUpsertRequest,
    db: Session = Depends(get_db),
) -> ProviderConfigModel:
    row = db.get(ProviderConfigModel, provider)
    if row is None:
        row = ProviderConfigModel(
            provider=provider,
            base_url=payload.base_url,
            timeout=payload.timeout,
            api_key=payload.api_key,
            extra_config=payload.extra_config,
        )
    else:
        row.base_url = payload.base_url
        row.timeout = payload.timeout
        row.api_key = payload.api_key
        row.extra_config = payload.extra_config
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
