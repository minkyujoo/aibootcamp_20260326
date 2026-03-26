from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SalesRepOut(BaseModel):
    id: int
    name: str
    email: str | None

    model_config = {"from_attributes": True}


class SalesRepCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str | None = Field(None, max_length=200)


class CompanyOut(BaseModel):
    id: int
    name: str
    biz_reg_no: str | None
    address: str | None
    industry: str | None
    dart_profile: str | None = None
    data_source_note: str
    sales_rep_id: int | None

    model_config = {"from_attributes": True}


class CompanyDetailOut(CompanyOut):
    opportunities_count: int = 0
    activities_count: int = 0


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    biz_reg_no: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=120)
    dart_profile: str | None = None
    data_source_note: str | None = Field(None, max_length=500)
    sales_rep_id: int | None = None


class CompanyPatch(BaseModel):
    sales_rep_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=200)
    biz_reg_no: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=120)
    dart_profile: str | None = None
    data_source_note: str | None = Field(None, max_length=500)


class OpportunityOut(BaseModel):
    id: int
    company_id: int
    name: str
    project_type: str
    stage: str
    win_probability: float
    sales_rep_id: int | None
    win_probability_rationale: str | None = Field(
        None,
        description="GET 단건·저장 응답에만 채움. 수주확률 규칙 요약(한국어).",
    )

    model_config = {"from_attributes": True}


class OpportunityPatch(BaseModel):
    stage: str | None = None
    sales_rep_id: int | None = None
    name: str | None = Field(None, max_length=200)
    project_type: str | None = Field(None, max_length=80)
    company_id: int | None = None


class OpportunityCreate(BaseModel):
    company_id: int
    name: str = Field(..., min_length=1, max_length=200)
    project_type: str = Field("SI", max_length=80)
    stage: str = Field("발굴", max_length=40)
    sales_rep_id: int | None = None


class ActivityOut(BaseModel):
    id: int
    kind: str
    subject: str
    body: str
    company_id: int | None
    opportunity_id: int | None
    sales_rep_id: int | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ActivityCreate(BaseModel):
    kind: Literal["mail", "meeting", "opinion", "note"] = "note"
    subject: str = Field("", max_length=300)
    body: str = Field("", max_length=200_000)
    company_id: int | None = None
    opportunity_id: int | None = None
    sales_rep_id: int | None = None


class MappingSuggestIn(BaseModel):
    text: str = Field(..., min_length=1)


class MappingSuggestOut(BaseModel):
    company_id: int | None
    opportunity_id: int | None
    company_score: float
    opportunity_score: float
    reason: str


class CrmAgentRunIn(BaseModel):
    message: str = Field("", max_length=8000)
    company_id: int | None = None
    opportunity_id: int | None = None
    activity_text: str | None = Field(None, max_length=20000)
    sales_rep_id: int | None = Field(None, ge=1, description="영업담당 id (담당자 단위 추천 등)")


class CrmAgentRunOut(BaseModel):
    agent: str
    answer: str
    context_summary: str
    cited_activity_ids: list[int] = []
    structured: dict | None = None


class CrmOrchestrateIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    current_menu: str | None = Field(
        None,
        description="companies|opportunities|reps|activities",
        max_length=40,
    )
    context_company_id: int | None = Field(
        None,
        ge=1,
        description="화면에서 선택된 고객사 id (이 고객사 맥락)",
    )
    context_opportunity_id: int | None = Field(
        None,
        ge=1,
        description="화면에서 선택된 사업기회 id",
    )
    context_sales_rep_id: int | None = Field(
        None,
        ge=1,
        description="화면에서 선택된 영업담당 id (이 담당자 맥락)",
    )


class CrmOrchestrateOut(BaseModel):
    routed_agent: str
    routing_reason: str
    answer: str
    context_summary: str
    cited_activity_ids: list[int] = []
    structured: dict | None = None


class ActionItemOut(BaseModel):
    id: int
    company_id: int
    opportunity_id: int | None
    title: str
    hint: str
    sort_order: int
    status: str
    result_subject: str | None
    result_body: str | None
    result_attachment_excerpt: str | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class ActionItemPatch(BaseModel):
    status: Literal["pending", "in_progress", "done"] | None = None
    result_subject: str | None = Field(None, max_length=300)
    result_body: str | None = None
