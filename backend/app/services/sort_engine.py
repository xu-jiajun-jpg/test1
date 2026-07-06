"""分拣规则引擎 — 完整性检测 + 异常流转 + 状态标记 + 任务分配"""
from datetime import datetime
from sqlalchemy.orm import Session
from ..models.sorting import SortingRule, SortingDecision
from ..models.ocr import OCRResult
from ..models.exception import ExceptionRecord
from ..models.operator import OperatorChute, Operator


def _check_integrity(tracking, phone, province, city, district) -> list:
    """检测运单信息完整性，返回缺失字段列表"""
    missing = []
    if not tracking: missing.append("运单号")
    if not phone: missing.append("电话")
    if not district: missing.append("分区")
    if not city: missing.append("城市")
    return missing


def _get_operators(target_chute: str, db: Session) -> list:
    """查询分拣口对应的分拣员"""
    from ..models.operator import OperatorChute, Operator
    oc_list = db.query(OperatorChute).filter(OperatorChute.chute_code == target_chute).all()
    names = []
    for oc in oc_list:
        op = db.query(Operator).filter(Operator.id == oc.operator_id).first()
        if op: names.append(op.name)
    return names


def _assign_to_chute(file_id: str, province: str, city: str, tracking: str,
                     district: str, target_chute: str, priority: int, rule_id: str,
                     status: str, db: Session) -> SortingDecision:
    """分拣到指定分拣口并记录（仅flush，由调用方统一commit）"""
    decision = SortingDecision(
        file_id=file_id, tracking_number=tracking,
        province=province, city=city, district=district,
        target_chute=target_chute, priority=priority, rule_id=rule_id,
        status=status, decision_time=datetime.utcnow(),
    )
    db.add(decision)
    db.flush()  # 返回ID但不提交
    return decision


class SortRuleEngine:
    """分拣决策引擎"""

    @staticmethod
    def decide(file_id: str, db: Session) -> dict:
        """执行分拣决策——含完整性检测与异常流转"""
        # 优先取人工确认过的，其次取置信度最高的
        ocr = (
            db.query(OCRResult)
            .filter(OCRResult.file_id == file_id)
            .order_by(
                OCRResult.status == "need_review",  # 人工确认优先(false=0排前)
            )
            .first()
        )
        if not ocr:
            return {"file_id": file_id, "status": "failed", "reason": "无OCR结果"}

        province = (ocr.province or "").strip()
        city = (ocr.city or "").strip()
        district = (ocr.district or "").strip()
        tracking = (ocr.tracking_number or "").strip()
        phone = (ocr.phone or "").strip()

        # ===== 1. 完整性检测 =====
        missing = _check_integrity(tracking, phone, province, city, district)

        if missing:
            # 分支1: 完全无法识别（无分区+无运单号）→ CH-006人工区
            if not district and not tracking:
                _assign_to_chute(file_id, province, city, "未知", district, "CH-006", 1, "R-MANUAL", "pending", db)
                db.add(ExceptionRecord(file_id=file_id, exception_type="ocr_incomplete",
                    detail=f"OCR完全无法识别，缺失: {', '.join(missing)}，已路由至人工识别区", status="pending"))
                db.commit()
                ops = _get_operators("CH-006", db)
                return {"file_id": file_id, "status": "pending", "target_chute": "CH-006",
                        "reason": f"完全无法识别({', '.join(missing)})，已转人工处理",
                        "assigned_operators": ops}

            # 分支2: 有分区但缺其他字段 → 暂按分区处理，同时创建异常待复核
            if district:
                _assign_to_chute(file_id, province, city, tracking or "未知", district, "CH-006", 1, "R-PARTIAL", "pending", db)
                db.add(ExceptionRecord(file_id=file_id, exception_type="ocr_incomplete",
                    detail=f"部分字段缺失: {', '.join(missing)}，已根据分区[{district}]暂分配至人工区", status="pending"))
                db.commit()
                ops = _get_operators("CH-006", db)
                return {"file_id": file_id, "status": "pending", "target_chute": "CH-006",
                        "district": district, "reason": f"部分缺失({', '.join(missing)})，暂按分区{district}→人工复核",
                        "assigned_operators": ops}

            # 分支3: 无分区有运单号 → 无法分拣，创建异常
            _assign_to_chute(file_id, province, city, tracking, district, "CH-006", 1, "R-MANUAL", "failed", db)
            db.add(ExceptionRecord(file_id=file_id, exception_type="ocr_incomplete",
                detail=f"缺分区({', '.join(missing)})，无法分拣，待人工处理", status="pending"))
            db.commit()
            return {"file_id": file_id, "status": "failed", "reason": f"无分区({', '.join(missing)})，无法分拣",
                    "assigned_operators": []}

        # ===== 2. 分拣规则按分区匹配（南昌大区） =====
        rules = []
        if district:
            rules = db.query(SortingRule).filter(
                SortingRule.district == district, SortingRule.is_active == True
            ).order_by(SortingRule.priority.asc()).all()

        if not rules:
            decision = _assign_to_chute(file_id, province, city, tracking, district,
                                        "CH-006", 1, "R-NO-RULE", "pending", db)
            db.add(ExceptionRecord(file_id=file_id, exception_type="no_match",
                detail=f"无[{district}]对应分拣规则，已转CH-006", status="pending"))
            db.commit()
            ops = _get_operators("CH-006", db)
            return {"file_id": file_id, "status": "pending", "district": district,
                    "target_chute": "CH-006", "reason": f"无[{district}]对应规则，已转CH-006",
                    "decision_id": decision.decision_id, "assigned_operators": ops}

        # ===== 3. 正常分拣 → pending状态等待派单 =====
        best_rule = rules[0]
        decision = _assign_to_chute(file_id, province, city, tracking, district,
                                    best_rule.target_chute, best_rule.priority,
                                    best_rule.rule_id, "pending", db)
        db.commit()

        # ===== 4. 任务分配给分拣口对应的分拣员 =====
        assigned_names = _get_operators(best_rule.target_chute, db)

        return {
            "file_id": file_id, "status": "pending",
            "tracking_number": tracking, "province": province, "city": city, "district": district,
            "target_chute": best_rule.target_chute, "priority": best_rule.priority,
            "decision_id": decision.decision_id,
            "assigned_operators": assigned_names,
            "message": f"已分拣至{best_rule.target_chute}" +
                       (f"，负责人: {', '.join(assigned_names)}" if assigned_names else ""),
        }
