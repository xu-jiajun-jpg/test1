"""
地区分区同步服务 — 当分区信息变更时，批量同步全链路关联数据
OCR结果 → 分拣决策 → 配送记录 → 内存追踪状态
"""
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from ..models.ocr import OCRResult
from ..models.sorting import SortingDecision
from ..models.logistics_records import DeliveryRecord
from ..services.delivery_tracking import _deliveries, _lock as _delivery_lock


# ===== 南昌市六大合法分区 =====
VALID_DISTRICTS = {"东湖区", "西湖区", "青云谱区", "青山湖区", "新建区", "红谷滩区"}

# 分区 → 分拣口映射（新建区归入东湖口处理）
DISTRICT_CHUTE_MAP = {
    "东湖区": "CH-001",
    "西湖区": "CH-002",
    "青云谱区": "CH-003",
    "青山湖区": "CH-004",
    "新建区": "CH-005",
    "红谷滩区": "CH-005",
}


def get_packages_by_district(district: str, db: Session) -> dict:
    """查询指定分区下的所有关联包裹（OCR→决策→配送）"""
    if district and district not in VALID_DISTRICTS:
        return {"valid": False, "message": f"分区[{district}]不在合法范围内", "data": {}}

    data = {
        "district": district,
        "ocr_records": [],
        "sorting_decisions": [],
        "delivery_records": [],
        "active_tracking": [],
    }

    # 1. OCR 记录
    ocr_query = db.query(OCRResult)
    if district:
        ocr_query = ocr_query.filter(OCRResult.district == district)
    ocs = ocr_query.all()
    for o in ocs:
        data["ocr_records"].append({
            "id": o.id, "file_id": o.file_id, "tracking_number": o.tracking_number,
            "province": o.province, "city": o.city, "district": o.district,
            "receiver_name": o.receiver_name, "phone": o.phone,
        })

    # 2. 分拣决策
    dec_query = db.query(SortingDecision)
    if district:
        dec_query = dec_query.filter(SortingDecision.district == district)
    decs = dec_query.limit(200).all()
    for d in decs:
        data["sorting_decisions"].append({
            "id": d.id, "decision_id": d.decision_id, "file_id": d.file_id,
            "tracking_number": d.tracking_number,
            "province": d.province, "city": d.city, "district": d.district,
            "target_chute": d.target_chute, "status": str(d.status),
        })

    # 3. 配送记录（按district+active）
    del_query = db.query(DeliveryRecord).filter(DeliveryRecord.active == 1)
    if district:
        del_query = del_query.filter(DeliveryRecord.district == district)
    dels = del_query.all()
    for d in dels:
        data["delivery_records"].append({
            "id": d.id, "tracking_number": d.tracking_number,
            "vehicle_id": d.vehicle_id, "origin": d.origin,
            "destination": d.destination, "district": d.district,
            "node_status": d.node_status, "node_status_name": d.node_status_name,
            "eta_minutes": d.eta_minutes,
        })

    # 4. 内存中活跃配送
    with _delivery_lock:
        for tn, pkg in _deliveries.items():
            dest = getattr(pkg, "destination", "")
            if district and district not in dest:
                continue
            if pkg.active_vehicle:
                data["active_tracking"].append({
                    "tracking_number": tn,
                    "vehicle_id": pkg.active_vehicle,
                    "destination": dest,
                    "node_status": getattr(pkg, "node_status", 0),
                    "node_status_name": getattr(pkg, "node_status_name", ""),
                    "eta_minutes": getattr(pkg, "eta_minutes", 0),
                })

    total = len(data["ocr_records"]) + len(data["sorting_decisions"]) + len(data["delivery_records"])
    data["summary"] = {
        "ocr_count": len(data["ocr_records"]),
        "decision_count": len(data["sorting_decisions"]),
        "delivery_count": len(data["delivery_records"]),
        "active_tracking_count": len(data["active_tracking"]),
        "total": total,
    }

    # 一致性状态
    if district:
        ocs_tns = {r["tracking_number"] for r in data["ocr_records"] if r["tracking_number"]}
        dec_tns = {r["tracking_number"] for r in data["sorting_decisions"] if r["tracking_number"]}
        del_tns = {r["tracking_number"] for r in data["delivery_records"] if r["tracking_number"]}
        data["consistency"] = {
            "orphan_decisions": sorted(dec_tns - ocs_tns),       # 有决策但无OCR
            "orphan_deliveries": sorted(del_tns - dec_tns),       # 有配送但无决策
            "missing_decisions": sorted(ocs_tns - dec_tns),       # 有OCR但无决策
            "is_consistent": (ocs_tns == dec_tns) and (dec_tns >= del_tns),
        }

    return {"valid": True, "message": f"分区[{district or '全部'}]共{total}条关联记录", "data": data}


def validate_district_consistency(db: Session) -> dict:
    """校验全库分区数据一致性，返回问题清单"""
    issues = {
        "ocr_missing_district": [],         # OCR有province+city但无district
        "decision_missing_district": [],     # 决策缺district
        "district_mismatch_ocr_decision": [], # OCR和决策district不一致
        "delivery_missing_district": [],     # 配送记录缺district
        "orphan_decisions": [],              # 有决策但无OCR
        "orphan_deliveries": [],             # 有配送但无决策
    }

    all_ocr = db.query(OCRResult).filter(OCRResult.province == "江西", OCRResult.city == "南昌").all()
    ocr_map = {o.tracking_number: o for o in all_ocr if o.tracking_number}

    for o in all_ocr:
        if not o.district:
            issues["ocr_missing_district"].append({
                "id": o.id, "tracking_number": o.tracking_number,
                "file_id": o.file_id,
            })

    all_dec = db.query(SortingDecision).all()
    for d in all_dec:
        if d.province == "江西" and d.city == "南昌" and not d.district:
            issues["decision_missing_district"].append({
                "id": d.id, "tracking_number": d.tracking_number,
                "decision_id": d.decision_id,
            })
        if d.tracking_number and d.tracking_number in ocr_map:
            ocr_dist = ocr_map[d.tracking_number].district
            if ocr_dist and d.district != ocr_dist:
                issues["district_mismatch_ocr_decision"].append({
                    "tracking_number": d.tracking_number,
                    "ocr_district": ocr_dist,
                    "decision_district": d.district,
                })

    all_del = db.query(DeliveryRecord).filter(DeliveryRecord.active == 1).all()
    dec_tns = {d.tracking_number for d in all_dec if d.tracking_number}
    for d in all_del:
        if not d.district:
            issues["delivery_missing_district"].append({
                "id": d.id, "tracking_number": d.tracking_number,
                "vehicle_id": d.vehicle_id,
            })
        if d.tracking_number and d.tracking_number not in dec_tns:
            if d.tracking_number not in ocr_map:
                issues["orphan_deliveries"].append({
                    "id": d.id, "tracking_number": d.tracking_number,
                })

    for d in all_dec:
        if d.tracking_number and d.tracking_number not in ocr_map:
            issues["orphan_decisions"].append({
                "id": d.id, "tracking_number": d.tracking_number,
                "decision_id": d.decision_id,
            })

    issue_count = sum(len(v) for v in issues.values())
    issues["total_issues"] = issue_count
    issues["is_clean"] = (issue_count == 0)
    return issues


def sync_district_change(from_district: str, to_district: str,
                         tracking_numbers: Optional[List[str]] = None,
                         db: Optional[Session] = None) -> dict:
    """批量同步分区变更：将from_district下所有包裹的分区改为to_district

    Args:
        from_district: 原分区（空字符串表示匹配所有无分区记录的包裹）
        to_district: 目标分区
        tracking_numbers: 可选，指定运单号列表（优先级高于from_district）
        db: 数据库会话

    Returns:
        {
            "success": True/False,
            "updated": {"ocr": N, "decision": N, "delivery": N, "memory": N},
            "errors": [...],
            "rollback_performed": True/False,
        }
    """
    if to_district not in VALID_DISTRICTS:
        return {"success": False, "message": f"目标分区[{to_district}]不在合法范围内",
                "valid_districts": list(VALID_DISTRICTS)}

    target_chute = DISTRICT_CHUTE_MAP[to_district]
    rollback_needed = False
    stats = {"ocr": 0, "decision": 0, "delivery": 0, "memory": 0}
    errors = []

    if db is None:
        from ..database import SessionLocal
        db = SessionLocal()
        _own_session = True
    else:
        _own_session = False

    try:
        # === 1. 更新 OCR 表 ===
        ocr_query = db.query(OCRResult)
        if tracking_numbers:
            ocr_query = ocr_query.filter(OCRResult.tracking_number.in_(tracking_numbers))
        else:
            if from_district:
                ocr_query = ocr_query.filter(OCRResult.district == from_district)
            else:
                # from_district 为空时，匹配 district 为空或 NULL 的记录
                from sqlalchemy import or_
                ocr_query = ocr_query.filter(or_(
                    OCRResult.district == "", OCRResult.district == None
                ))

        ocr_records = ocr_query.all()
        affected_tns = set()

        for ocr in ocr_records:
            old_val = ocr.district
            ocr.district = to_district
            stats["ocr"] += 1
            if ocr.tracking_number:
                affected_tns.add(ocr.tracking_number)
        db.flush()

        # === 2. 更新分拣决策表 ===
        dec_query = db.query(SortingDecision)
        if tracking_numbers:
            dec_query = dec_query.filter(SortingDecision.tracking_number.in_(tracking_numbers))
        elif affected_tns:
            dec_query = dec_query.filter(SortingDecision.tracking_number.in_(affected_tns))
        else:
            if from_district:
                dec_query = dec_query.filter(SortingDecision.district == from_district)
            else:
                from sqlalchemy import or_
                dec_query = dec_query.filter(or_(
                    SortingDecision.district == "", SortingDecision.district == None
                ))

        dec_records = dec_query.all()
        for dec in dec_records:
            dec.district = to_district
            # 如果分拣口需要更新（未分配到正确分拣口）
            if dec.target_chute != target_chute and dec.status in ("completed", "verified"):
                dec.target_chute = target_chute
            stats["decision"] += 1
            if dec.tracking_number:
                affected_tns.add(dec.tracking_number)
        db.flush()

        # === 3. 更新配送记录表 ===
        del_query = db.query(DeliveryRecord).filter(DeliveryRecord.active == 1)
        if tracking_numbers:
            del_query = del_query.filter(DeliveryRecord.tracking_number.in_(tracking_numbers))
        elif affected_tns:
            del_query = del_query.filter(DeliveryRecord.tracking_number.in_(affected_tns))
        else:
            if from_district:
                del_query = del_query.filter(DeliveryRecord.district == from_district)
            else:
                from sqlalchemy import or_
                del_query = del_query.filter(or_(
                    DeliveryRecord.district == "", DeliveryRecord.district == None
                ))

        del_records = del_query.all()
        for dr in del_records:
            dr.district = to_district
            # 更新 destination 字符串，确保包含分区信息
            old_dest = dr.destination or ""
            # 去掉旧分区后缀，加上新分区
            base_dest = old_dest
            for d in VALID_DISTRICTS:
                if old_dest.endswith(d):
                    base_dest = old_dest[:-len(d)]
                    break
            dr.destination = base_dest + to_district
            stats["delivery"] += 1
        db.flush()

        # === 4. 更新内存中的配送追踪 ===
        with _delivery_lock:
            for tn, pkg in list(_deliveries.items()):
                if tracking_numbers and tn not in tracking_numbers:
                    continue
                if hasattr(pkg, "destination"):
                    old_dest = pkg.destination or ""
                    for d in VALID_DISTRICTS:
                        if old_dest.endswith(d):
                            old_dest = old_dest[:-len(d)]
                            break
                    new_dest = old_dest + to_district
                    pkg.destination = new_dest
                    stats["memory"] += 1

        db.commit()

    except Exception as e:
        rollback_needed = True
        errors.append({"phase": "commit", "error": str(e)})
        try:
            db.rollback()
        except:
            pass
        return {
            "success": False,
            "message": f"同步失败，已回滚: {str(e)}",
            "updated": stats,
            "errors": errors,
            "rollback_performed": True,
        }
    finally:
        if _own_session:
            db.close()

    affected_count = len(affected_tns) if affected_tns else 0
    total_updated = stats["ocr"] + stats["decision"] + stats["delivery"] + stats["memory"]

    return {
        "success": True,
        "message": f"分区[{from_district or '(空)'}]→[{to_district}]同步完成: {total_updated}条记录({affected_count}个包裹)",
        "from_district": from_district,
        "to_district": to_district,
        "target_chute": target_chute,
        "affected_tracking_numbers": affected_count,
        "updated": stats,
        "errors": errors,
        "rollback_performed": rollback_needed,
    }


def auto_fix_consistency(db: Session) -> dict:
    """自动修复已知的一致性问题（补填缺失的 district）"""
    fixes = {"ocr_filled": 0, "decision_filled": 0, "delivery_filled": 0}

    try:
        # 补充 OCR 中缺失的 district（从 tracking_number 匹配已有数据）
        from sqlalchemy import or_
        blank_ocrs = db.query(OCRResult).filter(
            OCRResult.province == "江西", OCRResult.city == "南昌",
            or_(OCRResult.district == "", OCRResult.district == None)
        ).all()

        for ocr in blank_ocrs:
            if ocr.tracking_number:
                # 尝试从同 tracking_number 的 OCR 记录中推断 district
                ref = db.query(OCRResult).filter(
                    OCRResult.tracking_number == ocr.tracking_number,
                    OCRResult.district != "",
                    OCRResult.district != None,
                ).first()
                if ref:
                    ocr.district = ref.district
                    fixes["ocr_filled"] += 1
        db.flush()

        # 补充分拣决策中缺失的 district
        blank_decs = db.query(SortingDecision).filter(
            SortingDecision.province == "江西", SortingDecision.city == "南昌",
            or_(SortingDecision.district == "", SortingDecision.district == None)
        ).all()

        for dec in blank_decs:
            if dec.tracking_number:
                ocr = db.query(OCRResult).filter(
                    OCRResult.tracking_number == dec.tracking_number
                ).first()
                if ocr and ocr.district:
                    dec.district = ocr.district
                    fixes["decision_filled"] += 1
        db.flush()

        # 补充配送记录中缺失的 district
        blank_dels = db.query(DeliveryRecord).filter(
            DeliveryRecord.active == 1,
            or_(DeliveryRecord.district == "", DeliveryRecord.district == None)
        ).all()

        for dr in blank_dels:
            if dr.tracking_number:
                dec = db.query(SortingDecision).filter(
                    SortingDecision.tracking_number == dr.tracking_number
                ).first()
                if dec and dec.district:
                    dr.district = dec.district
                    dr.destination = (dr.destination or "").rstrip("".join(VALID_DISTRICTS)) + dec.district
                    fixes["delivery_filled"] += 1

        db.commit()
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"自动修复失败: {e}", "fixes": fixes}

    total = sum(fixes.values())
    return {
        "success": True,
        "message": f"自动修复完成: {total}条记录",
        "fixes": fixes,
    }
