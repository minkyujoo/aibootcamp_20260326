"""추천 Action item 시드 (기존 DB에도 누락분만 채움)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from rag_agent.crm.action_templates import COMPANY_LEVEL_ACTIONS, actions_for_opportunity
from rag_agent.crm.models import ActionItem, Company, Opportunity


def seed_actions_for_opportunity(db: Session, o: Opportunity) -> None:
    n = db.query(ActionItem).filter(ActionItem.opportunity_id == o.id).count()
    if n > 0:
        return
    for i, (title, hint) in enumerate(actions_for_opportunity(o.stage)):
        db.add(
            ActionItem(
                company_id=o.company_id,
                opportunity_id=o.id,
                title=title,
                hint=hint,
                sort_order=i,
                status="pending",
            )
        )


def seed_actions_for_company_account(db: Session, company_id: int) -> None:
    n = (
        db.query(ActionItem)
        .filter(
            ActionItem.company_id == company_id,
            ActionItem.opportunity_id.is_(None),
        )
        .count()
    )
    if n > 0:
        return
    for i, (title, hint) in enumerate(COMPANY_LEVEL_ACTIONS):
        db.add(
            ActionItem(
                company_id=company_id,
                opportunity_id=None,
                title=title,
                hint=hint,
                sort_order=i,
                status="pending",
            )
        )


def ensure_action_items(db: Session) -> None:
    for o in db.query(Opportunity).order_by(Opportunity.id).all():
        seed_actions_for_opportunity(db, o)
    for c in db.query(Company).order_by(Company.id).all():
        seed_actions_for_company_account(db, c.id)
    db.commit()
