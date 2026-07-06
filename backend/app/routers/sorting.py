"""分拣决策路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..middleware.auth_middleware import get_current_user_id
from ..services.sort_engine import SortRuleEngine
from ..websocket.manager import manager
from ..models.sorting import SortingDecision, SortingRule, SortingChute

router = APIRouter(prefix="/api/sort", tags=["分拣"])


@router.post("/decide/{file_id}")
async def trigger_decision(
    file_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """对已识别的文件执行分拣决策"""
    # 检查是否已存在有效决策，避免重复创建
    existing = db.query(SortingDecision).filter(
        SortingDecision.file_id == file_id,
        SortingDecision.status.in_(["pending", "dispatched", "accepted", "processing", "completed"])
    ).first()
    if existing:
        return {"code": 200, "message": "已有决策", "data": {
            "file_id": file_id, "status": existing.status,
            "target_chute": existing.target_chute, "decision_id": existing.decision_id
        }}

    result = SortRuleEngine.decide(file_id, db)

    # WebSocket 推送
    if result["status"] in ("pending", "dispatched", "accepted", "processing"):
        await manager.broadcast_sort_result(result)

    return {"code": 200, "message": "决策完成", "data": result}


@router.get("/decisions")
def list_decisions(
    page: int = 1,
    page_size: int = 20,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """分拣决策列表 — 操作员仅看到所属分拣口的数据"""
    from ..models.user import User
    from sqlalchemy import or_

    user = db.query(User).filter(User.id == user_id).first()
    is_operator = user and user.role in ("operator", "supervisor")

    query = db.query(SortingDecision)
    if is_operator:
        # 操作员：通过 User.operator_id 或 display_name 模糊匹配获取分拣口
        from ..models.operator import Operator, OperatorChute
        from sqlalchemy import func

        operator = None
        if user.operator_id:
            operator = db.query(Operator).filter(Operator.id == user.operator_id).first()
        else:
            operator = db.query(Operator).filter(
                (Operator.name == user.display_name)
                | (func.instr(user.display_name, Operator.name) > 0)
            ).first()

        if operator:
            chutes = db.query(OperatorChute).filter(
                OperatorChute.operator_id == operator.id
            ).all()
            chute_codes = [c.chute_code for c in chutes]
            if chute_codes:
                query = query.filter(SortingDecision.target_chute.in_(chute_codes))

    total = query.count()
    decisions = (
        query
        .order_by(SortingDecision.decision_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "decision_id": d.decision_id,
            "file_id": d.file_id,
            "tracking_number": d.tracking_number,
            "province": d.province,
            "city": d.city,
            "district": d.district or "",
            "target_chute": d.target_chute,
            "priority": d.priority,
            "status": d.status,
            "decision_time": d.decision_time.isoformat() if d.decision_time else None,
        }
        for d in decisions
    ]
    from ..utils.response import paginated
    return paginated(items, total, page, page_size)


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    """分拣规则列表"""
    rules = db.query(SortingRule).filter(SortingRule.is_active == True).order_by(SortingRule.priority).all()
    return {
        "code": 200,
        "data": [
            {
                "rule_id": r.rule_id,
                "province": r.province,
                "city": r.city,
                "district": r.district or "",
                "target_chute": r.target_chute,
                "priority": r.priority,
                "description": r.description,
            }
            for r in rules
        ],
    }


@router.post("/rules")
def create_rule(
    rule: dict,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """新增分拣规则"""
    r = SortingRule(
        rule_id=rule.get("rule_id"),
        province=rule.get("province", ""),
        city=rule.get("city", ""),
        district=rule.get("district", ""),
        target_chute=rule.get("target_chute"),
        priority=rule.get("priority", 99),
        description=rule.get("description"),
    )
    db.add(r)
    db.commit()
    return {"code": 200, "message": "规则创建成功", "data": {"id": r.id}}
