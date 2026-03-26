"""초기 시드: 영업담당 10명, SK 멤버사 20개(공공·DART 참고), 고객사별 IT 사업기회 3~8건."""

from __future__ import annotations

import os
import random

from sqlalchemy.orm import Session

from rag_agent.crm.companies_data import IT_OPPORTUNITY_TEMPLATES, SK_COMPANIES
from rag_agent.crm.models import Activity, Company, Opportunity, SalesRep
from rag_agent.crm.probability import recalculate_opportunity

_REP_NAMES = [
    "김영업",
    "이기회",
    "박담당",
    "최고객",
    "정계약",
    "한제안",
    "조협상",
    "윤발굴",
    "강니즈",
    "임수주",
]


def _wipe_seedable_crm_domain(db: Session) -> None:
    """고객사·사업기회·활동·액션만 삭제(영업담당은 유지)."""
    from rag_agent.crm.models import ActionItem

    db.query(ActionItem).delete()
    db.query(Activity).delete()
    db.query(Opportunity).delete()
    db.query(Company).delete()
    db.commit()


def _ensure_sales_reps(db: Session) -> list[SalesRep]:
    existing = db.query(SalesRep).order_by(SalesRep.id).all()
    if existing:
        return existing
    reps: list[SalesRep] = []
    for i, name in enumerate(_REP_NAMES):
        r = SalesRep(name=name, email=f"rep{i + 1:02d}@example.local")
        db.add(r)
        reps.append(r)
    db.flush()
    return db.query(SalesRep).order_by(SalesRep.id).all()


def ensure_seed(db: Session) -> None:
    rebuild = os.getenv("CRM_REBUILD_SEED", "").strip().lower() in ("1", "true", "yes")
    if rebuild:
        _wipe_seedable_crm_domain(db)

    if db.query(Company).first() is not None:
        return

    reps = _ensure_sales_reps(db)

    companies: list[Company] = []
    for idx, row in enumerate(SK_COMPANIES):
        rep = reps[idx % len(reps)]
        note = row.data_source_note[:500] if len(row.data_source_note) > 500 else row.data_source_note
        c = Company(
            name=row.name,
            biz_reg_no=row.biz_reg_no,
            address=row.address[:500] if row.address else None,
            industry=row.industry[:120] if row.industry else None,
            dart_profile=row.dart_profile,
            data_source_note=note,
            sales_rep_id=rep.id,
        )
        db.add(c)
        companies.append(c)
    db.flush()

    for ci, c in enumerate(companies):
        rng = random.Random(7000 + ci)
        n_opps = rng.randint(3, 8)
        indices = rng.sample(range(len(IT_OPPORTUNITY_TEMPLATES)), k=n_opps)
        for ti in indices:
            title, ptype, stage = IT_OPPORTUNITY_TEMPLATES[ti]
            o = Opportunity(
                company_id=c.id,
                name=f"{c.name} — {title}",
                project_type=ptype,
                stage=stage,
                win_probability=0.15,
                sales_rep_id=c.sales_rep_id,
            )
            db.add(o)
    db.flush()

    sample = (
        "요구사항 정리 회의에서 범위·일정·예산을 협의했습니다. "
        "계약 조건(라이선스·유지보수)은 차주 재논의 예정입니다."
    )
    for c in companies[:5]:
        db.add(
            Activity(
                kind="meeting",
                subject=f"{c.name} IT 로드맵 워크숍",
                body=sample,
                company_id=c.id,
                sales_rep_id=c.sales_rep_id,
            )
        )
    db.commit()

    for o in db.query(Opportunity).all():
        recalculate_opportunity(db, o)
