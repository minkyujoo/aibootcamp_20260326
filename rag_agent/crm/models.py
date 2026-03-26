from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_agent.crm.db import Base


class SalesRep(Base):
    __tablename__ = "sales_reps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    companies = relationship("Company", back_populates="sales_rep")
    opportunities = relationship("Opportunity", back_populates="sales_rep")
    activities = relationship("Activity", back_populates="sales_rep")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    biz_reg_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dart_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_source_note: Mapped[str] = mapped_column(
        String(500),
        default="공공데이터포털(data.go.kr) 연동 전 시드 데이터 — SK 멤버사 중심 20개사",
    )
    sales_rep_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=True
    )

    sales_rep = relationship("SalesRep", back_populates="companies")
    opportunities = relationship("Opportunity", back_populates="company")
    activities = relationship("Activity", back_populates="company")
    action_items = relationship(
        "ActionItem", back_populates="company", cascade="all, delete-orphan"
    )


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_type: Mapped[str] = mapped_column(String(80), default="SI")
    stage: Mapped[str] = mapped_column(String(40), default="발굴")
    win_probability: Mapped[float] = mapped_column(Float, default=0.15)
    sales_rep_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=True
    )

    company = relationship("Company", back_populates="opportunities")
    sales_rep = relationship("SalesRep", back_populates="opportunities")
    activities = relationship("Activity", back_populates="opportunity")
    action_items = relationship(
        "ActionItem", back_populates="opportunity", cascade="all, delete-orphan"
    )


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True
    )
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True
    )
    sales_rep_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="activities")
    opportunity = relationship("Opportunity", back_populates="activities")
    sales_rep = relationship("SalesRep", back_populates="activities")


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    hint: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | in_progress | done
    result_subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    result_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_attachment_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="action_items")
    opportunity = relationship("Opportunity", back_populates="action_items")
