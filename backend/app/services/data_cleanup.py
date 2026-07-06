"""
数据清理服务 — 删除非南昌目的地包裹、重复数据、孤立记录
确保数据库中所有包裹目的地严格限定为南昌市各区
"""
from typing import Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.ocr import OCRResult
from ..models.sorting import SortingDecision
from ..models.logistics_records import DeliveryRecord
from ..models.upload import UploadRecord
from ..models.barcode import BarcodeResult
from ..models.exception import ExceptionRecord

# 南昌市合法分区
VALID_DISTRICTS = {"东湖区", "西湖区", "青云谱区", "青山湖区", "新建区", "红谷滩区"}


def analyze_data_quality(db: Session) -> dict:
    """分析数据库中包裹数据质量，返回问题统计"""
    issues = {}

    # 1. 非南昌省份包裹
    non_jx = db.query(OCRResult).filter(
        OCRResult.province.isnot(None),
        OCRResult.province != "",
        OCRResult.province != "江西"
    ).count()
    issues["non_nanchang_province"] = non_jx

    # 2. 非南昌城市包裹
    non_nc = db.query(OCRResult).filter(
        OCRResult.city.isnot(None),
        OCRResult.city != "",
        ~OCRResult.city.like("%南昌%")
    ).count()
    issues["non_nanchang_city"] = non_nc

    # 3. 非法分区包裹
    invalid_dist = db.query(OCRResult).filter(
        OCRResult.district.isnot(None),
        OCRResult.district != "",
        ~OCRResult.district.in_(VALID_DISTRICTS)
    ).count()
    issues["invalid_district"] = invalid_dist

    # 4. 重复运单号
    dup_tns = (
        db.query(OCRResult.tracking_number, func.count(OCRResult.id).label("cnt"))
        .filter(OCRResult.tracking_number.isnot(None), OCRResult.tracking_number != "")
        .group_by(OCRResult.tracking_number)
        .having(func.count(OCRResult.id) > 1)
        .all()
    )
    issues["duplicate_tracking_count"] = len(dup_tns)
    issues["duplicate_record_count"] = sum(r.cnt - 1 for r in dup_tns)

    # 5. 孤立分拣决策（无对应OCR）
    all_ocr_tns = set(
        row[0] for row in db.query(OCRResult.tracking_number)
        .filter(OCRResult.tracking_number.isnot(None), OCRResult.tracking_number != "")
        .all()
    )
    orphan_dec = db.query(SortingDecision).filter(
        SortingDecision.tracking_number.isnot(None),
        SortingDecision.tracking_number != "",
        ~SortingDecision.tracking_number.in_(all_ocr_tns) if all_ocr_tns else True
    ).count()
    issues["orphan_decisions"] = orphan_dec

    # 6. 孤立配送记录（无对应决策）
    all_dec_tns = set(
        row[0] for row in db.query(SortingDecision.tracking_number)
        .filter(SortingDecision.tracking_number.isnot(None), SortingDecision.tracking_number != "")
        .all()
    )
    orphan_del = db.query(DeliveryRecord).filter(
        DeliveryRecord.tracking_number.isnot(None),
        DeliveryRecord.tracking_number != "",
        ~DeliveryRecord.tracking_number.in_(all_dec_tns) if all_dec_tns else True
    ).count()
    issues["orphan_deliveries"] = orphan_del

    # 7. 总OCR记录数
    total_ocr = db.query(OCRResult).count()
    total_dec = db.query(SortingDecision).count()
    total_del = db.query(DeliveryRecord).count()
    issues["total_ocr"] = total_ocr
    issues["total_decisions"] = total_dec
    issues["total_deliveries"] = total_del

    total_issues = non_jx + non_nc + invalid_dist + len(dup_tns) + orphan_dec + orphan_del
    issues["total_issues"] = total_issues
    issues["is_clean"] = (total_issues == 0)

    return issues


def cleanup_invalid_packages(db: Session, dry_run: bool = True) -> dict:
    """清理非南昌目的地包裹及相关联数据

    Args:
        db: 数据库会话
        dry_run: True=仅统计不删除，False=实际执行删除

    清理顺序（按外键依赖反向）:
    1. DeliveryRecord (无外键)
    2. SortingDecision (无外键)
    3. BarcodeResult (关联UploadRecord)
    4. ExceptionRecord (关联UploadRecord)
    5. OCRResult (关联UploadRecord)
    6. UploadRecord (根记录)
    """
    result = {
        "dry_run": dry_run,
        "deleted": {},
        "kept": {},
        "errors": [],
    }

    try:
        # ===== 1. 找出所有非南昌的 OCR 记录 =====
        invalid_ocr_ids = set()
        invalid_ocr_tns = set()
        invalid_file_ids = set()

        # 非江西省份
        for ocr in db.query(OCRResult).filter(
            OCRResult.province.isnot(None), OCRResult.province != "", OCRResult.province != "江西"
        ).all():
            invalid_ocr_ids.add(ocr.id)
            if ocr.tracking_number: invalid_ocr_tns.add(ocr.tracking_number)
            if ocr.file_id: invalid_file_ids.add(ocr.file_id)

        # 非南昌城市
        for ocr in db.query(OCRResult).filter(
            OCRResult.city.isnot(None), OCRResult.city != "", ~OCRResult.city.like("%南昌%")
        ).all():
            invalid_ocr_ids.add(ocr.id)
            if ocr.tracking_number: invalid_ocr_tns.add(ocr.tracking_number)
            if ocr.file_id: invalid_file_ids.add(ocr.file_id)

        # 非法分区
        valid_list = list(VALID_DISTRICTS)
        for ocr in db.query(OCRResult).filter(
            OCRResult.district.isnot(None), OCRResult.district != "",
            ~OCRResult.district.in_(valid_list)
        ).all():
            invalid_ocr_ids.add(ocr.id)
            if ocr.tracking_number: invalid_ocr_tns.add(ocr.tracking_number)
            if ocr.file_id: invalid_file_ids.add(ocr.file_id)

        result["invalid_ocr_count"] = len(invalid_ocr_ids)
        result["invalid_tracking_numbers"] = len(invalid_ocr_tns)
        result["invalid_file_ids"] = len(invalid_file_ids)

        if not invalid_ocr_ids and not invalid_ocr_tns:
            result["message"] = "无需要清理的数据"
            return result

        # ===== 2. 删除关联 Decision (按 tracking_number) =====
        if invalid_ocr_tns:
            decs = db.query(SortingDecision).filter(
                SortingDecision.tracking_number.in_(invalid_ocr_tns)
            ).all()
            result["related_decisions"] = len(decs)
            if not dry_run:
                for d in decs: db.delete(d)

        # ===== 3. 删除关联 DeliveryRecord =====
        if invalid_ocr_tns:
            dels = db.query(DeliveryRecord).filter(
                DeliveryRecord.tracking_number.in_(invalid_ocr_tns)
            ).all()
            result["related_deliveries"] = len(dels)
            if not dry_run:
                for d in dels: db.delete(d)

        # ===== 4. 删除关联 BarcodeResult =====
        if invalid_file_ids:
            bars = db.query(BarcodeResult).filter(
                BarcodeResult.file_id.in_(invalid_file_ids)
            ).all()
            result["related_barcodes"] = len(bars)
            if not dry_run:
                for b in bars: db.delete(b)

        # ===== 5. 删除关联 ExceptionRecord =====
        if invalid_file_ids:
            excs = db.query(ExceptionRecord).filter(
                ExceptionRecord.file_id.in_(invalid_file_ids)
            ).all()
            result["related_exceptions"] = len(excs)
            if not dry_run:
                for e in excs: db.delete(e)

        # ===== 6. 删除 OCRResult =====
        if invalid_ocr_ids:
            result["deleted_ocr"] = len(invalid_ocr_ids)
            if not dry_run:
                for ocr_id in invalid_ocr_ids:
                    db.query(OCRResult).filter(OCRResult.id == ocr_id).delete()

        # ===== 7. 删除 UploadRecord =====
        if invalid_file_ids:
            result["deleted_uploads"] = len(invalid_file_ids)
            if not dry_run:
                for fid in invalid_file_ids:
                    db.query(UploadRecord).filter(UploadRecord.file_id == fid).delete()

        # ===== 8. 去重：保留最新记录，删除旧的 =====
        dup_deleted = 0
        dup_tns = (
            db.query(OCRResult.tracking_number, func.count(OCRResult.id).label("cnt"))
            .filter(OCRResult.tracking_number.isnot(None), OCRResult.tracking_number != "")
            .group_by(OCRResult.tracking_number)
            .having(func.count(OCRResult.id) > 1)
            .all()
        )
        for (tn, _) in dup_tns:
            records = db.query(OCRResult).filter(
                OCRResult.tracking_number == tn
            ).order_by(OCRResult.id.desc()).all()
            # 保留最新的（第一个），删除其余
            for rec in records[1:]:
                # 删除关联
                if not dry_run:
                    db.query(SortingDecision).filter(
                        SortingDecision.file_id == rec.file_id
                    ).delete()
                    db.query(DeliveryRecord).filter(
                        DeliveryRecord.tracking_number == rec.tracking_number
                    ).delete()
                    db.query(OCRResult).filter(OCRResult.id == rec.id).delete()
                dup_deleted += 1

        result["duplicates_removed"] = dup_deleted

        # ===== 9. 清理孤立记录 =====
        all_tns = set(
            row[0] for row in db.query(OCRResult.tracking_number)
            .filter(OCRResult.tracking_number.isnot(None), OCRResult.tracking_number != "")
            .all()
        )
        if all_tns:
            orphan1 = db.query(SortingDecision).filter(
                ~SortingDecision.tracking_number.in_(all_tns)
            ).delete(synchronize_session=False) if not dry_run else 0
            result["orphan_decisions_cleaned"] = orphan1

        all_dec_tns = set(
            row[0] for row in db.query(SortingDecision.tracking_number)
            .filter(SortingDecision.tracking_number.isnot(None), SortingDecision.tracking_number != "")
            .all()
        )
        if all_dec_tns:
            orphan2 = db.query(DeliveryRecord).filter(
                ~DeliveryRecord.tracking_number.in_(all_dec_tns)
            ).delete(synchronize_session=False) if not dry_run else 0
            result["orphan_deliveries_cleaned"] = orphan2

        if not dry_run:
            db.commit()
            result["message"] = "清理完成"

        # 最终统计
        after_ocr = db.query(OCRResult).count()
        after_dec = db.query(SortingDecision).count()
        after_del = db.query(DeliveryRecord).count()
        result["after_ocr"] = after_ocr
        result["after_decisions"] = after_dec
        result["after_deliveries"] = after_del
        result["total_deleted"] = sum(
            result.get(k, 0) for k in [
                "deleted_ocr", "deleted_uploads", "duplicates_removed",
                "related_decisions", "related_deliveries", "related_barcodes",
                "related_exceptions", "orphan_decisions_cleaned", "orphan_deliveries_cleaned",
            ]
        )

    except Exception as e:
        if not dry_run:
            db.rollback()
        result["errors"].append(str(e))

    return result
