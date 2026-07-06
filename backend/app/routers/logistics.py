"""物流配送管理路由 — 装箱 / 路径规划 / 发车 / 追踪 / 分区管理"""
import uuid, json, random
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.ocr import OCRResult
from ..models.sorting import SortingDecision
from ..models.logistics_records import VehicleRecord, DeliveryRecord
from ..config import ORIGIN_CITY, ORIGIN_LNG, ORIGIN_LAT
from ..services.load_packer import pack_packages, Package
from ..services.aco_planner import aco_tsp, City, DISTRICT_COORDS
from ..services.delivery_tracking import (
    bind_packages_to_vehicle, get_binding_summary, get_vehicle_packages,
    _deliveries, _lock as _delivery_lock,
    start_vehicle_simulation, get_vehicle_state,
)
from ..services.district_sync import (
    sync_district_change, validate_district_consistency,
    get_packages_by_district, auto_fix_consistency,
    VALID_DISTRICTS, DISTRICT_CHUTE_MAP,
)

router = APIRouter(prefix="/api/logistics", tags=["物流配送管理"])


# ========== 装箱优化 ==========

class PackRequest(BaseModel):
    destinations: list[str] = Field(default_factory=list)
    container: Optional[dict] = Field(default=None)
    limit: int = Field(default=80, ge=5, le=200)
    decision_ids: list[str] = Field(default_factory=list)


@router.post("/pack")
def pack_api(req: PackRequest, db: Session = Depends(get_db)):
    vehicle_size = req.container or {"length": 420, "width": 230, "height": 220}

    # 优先用指定 decision_ids（操作员选中的包裹）
    if req.decision_ids:
        decisions = db.query(SortingDecision).filter(
            SortingDecision.decision_id.in_(req.decision_ids)
        ).all()
    else:
        query = db.query(SortingDecision).filter(SortingDecision.status.in_(["completed", "verified"]))
        if req.destinations:
            from sqlalchemy import or_
            filters = []
            for d in req.destinations:
                filters.append(SortingDecision.district == d)
                filters.append(SortingDecision.target_chute.like(f"%{d}%"))
            query = query.filter(or_(*filters))
        decisions = query.limit(req.limit).all()
    if not decisions:
        return {"code": 200, "message": "无可装箱包裹", "data": {"fill_rate": 0, "placed": [], "unplaced": [], "placed_count": 0, "unplaced_count": 0, "destination_groups": [], "bindable_tracking_numbers": []}}

    total_pkgs = []
    dest_counter = {}
    for d in decisions:
        l = round(random.uniform(20, 60), 1)
        w = round(random.uniform(15, 45), 1)
        h = round(random.uniform(10, 40), 1)
        dest = d.district or "未知"
        dest_counter[dest] = dest_counter.get(dest, 0) + 1
        total_pkgs.append({
            "package": Package(
                id=d.file_id[:8] if d.file_id else uuid.uuid4().hex[:8],
                tracking_number=d.tracking_number or f"PKG{len(total_pkgs)+1:03d}",
                l=l, w=w, h=h,
            ),
            "destination": dest,
            "province": d.district or d.province or "", "city": d.city or "", "district": d.district or "",
        })

    result = pack_packages([p["package"] for p in total_pkgs], vehicle_size)
    placed_tns = [p.pkg.tracking_number for p in result.placed]
    dest_groups = [{"dest": k, "count": v} for k, v in sorted(dest_counter.items(), key=lambda x: -x[1])]
    return {
        "code": 200, "message": f"装箱完成，填充率{result.fill_rate}%",
        "data": {
            "fill_rate": result.fill_rate, "total_volume": round(result.total_volume, 1),
            "used_volume": round(result.used_volume, 1),
            "placed_count": len(result.placed), "unplaced_count": len(result.unplaced),
            "placed": [{"id": p.pkg.id, "tracking_number": p.pkg.tracking_number,
                        "x": round(p.x, 1), "y": round(p.y, 1), "z": round(p.z, 1),
                        "rotation": p.rotation, "l": round(p.l_used, 1),
                        "w": round(p.w_used, 1), "h": round(p.h_used, 1),
                        "destination": next((t["destination"] for t in total_pkgs if t["package"].tracking_number == p.pkg.tracking_number), "")} for p in result.placed],
            "unplaced": [{"id": p.id, "tracking_number": p.tracking_number,
                          "l": p.l, "w": p.w, "h": p.h} for p in result.unplaced],
            "total_packages": [{"tracking_number": p["package"].tracking_number,
                                "destination": p["destination"],
                                "district": p.get("district", "")} for p in total_pkgs],
            "destination_groups": dest_groups,
            "bindable_tracking_numbers": placed_tns,
            "vehicle_size": vehicle_size,
        },
    }


# ========== 路径规划 ==========

class RoutePlanRequest(BaseModel):
    cities: list[str] = Field(default_factory=list)


@router.post("/route-plan")
def plan_route(req: RoutePlanRequest, iterations: int = Query(default=50, le=200)):
    cities_input = req.cities or [k for k in DISTRICT_COORDS if k != "南昌"]
    all_names = ["南昌"] + [c for c in cities_input if c in DISTRICT_COORDS and c != "南昌"]
    if len(all_names) < 2:
        return {"code": 200, "data": {"path": all_names, "total_distance_km": 0}}
    cities = [City(name=n, lng=c[0], lat=c[1]) for n, c in DISTRICT_COORDS.items() if n in all_names]
    result = aco_tsp(cities, n_iterations=iterations)
    return {
        "code": 200, "message": f"路径规划完成，总距离{result.total_distance_km}km",
        "data": {
            "path": result.path, "total_distance_km": result.total_distance_km,
            "waypoints": [{"lng": w[0], "lat": w[1], "name": w[2]} for w in result.waypoints],
            "iterations": result.iterations, "convergence": result.convergence,
        },
    }


# ========== 可用包裹列表 ==========

@router.get("/packages/available")
def list_available(db: Session = Depends(get_db)):
    decisions = db.query(SortingDecision).filter(
        SortingDecision.status.in_(["completed", "verified"])
    ).order_by(SortingDecision.decision_time.desc()).limit(100).all()

    bound_tns, delivered_tns = set(), set()
    with _delivery_lock:
        for tn, pkg in _deliveries.items():
            if pkg.active_vehicle: bound_tns.add(tn)
            if pkg.node_status >= 4: delivered_tns.add(tn)

    packages = []
    for d in decisions:
        tn = d.tracking_number or ""
        if not tn or tn in delivered_tns: continue
        is_bound = tn in bound_tns
        bv = ""; ds = "待绑定"
        if is_bound:
            with _delivery_lock:
                pd = _deliveries.get(tn)
                if pd:
                    bv = pd.active_vehicle
                    s = ["已揽收", "分拣装车", "出库配送", "区内到达", "已签收"]
                    ds = s[pd.node_status] if pd.node_status < len(s) else "未知"
        packages.append({
            "tracking_number": tn, "province": d.district or d.province or "", "city": d.city or "",
            "district": d.district or "", "target_chute": getattr(d, "target_chute", ""),
            "is_bound": is_bound, "bound_vehicle": bv, "delivery_status": ds,
        })
    return {"code": 200, "message": f"共{len(packages)}个可用包裹", "data": packages}


# ========== 发车 ==========

class DepartRequest(BaseModel):
    vehicle_id: str = Field(default="")
    tracking_numbers: list[str]
    waypoints: list[dict] = Field(default_factory=list)   # [{lng, lat, name}]
    speed_kmh: float = Field(default=30, ge=5, le=80)


@router.post("/depart")
def depart(req: DepartRequest, db: Session = Depends(get_db)):
    vehicle_id = req.vehicle_id.strip() or f"V{datetime.now().strftime('%Y%m%d%H%M%S')}"
    tns = [t.strip() for t in req.tracking_numbers if t.strip()]
    if not tns: raise HTTPException(400, "运单号列表不能为空")

    ocr_list = db.query(OCRResult).filter(OCRResult.tracking_number.in_(tns)).all()
    destinations = {}
    for ocr in ocr_list:
        parts = ["江西", "南昌市"]
        dest = "".join(parts).strip()
        if ocr.district: dest += ocr.district
        if dest: destinations[ocr.tracking_number] = dest

    bind_results = bind_packages_to_vehicle(tns, vehicle_id, destinations)
    bound_tns = [r["tracking_number"] for r in bind_results if r.get("bound")]

    if bound_tns:
        existing_tns = {dr.tracking_number for dr in db.query(DeliveryRecord).filter(
            DeliveryRecord.tracking_number.in_(bound_tns), DeliveryRecord.active == 1).all()}
        for tn in bound_tns:
            if tn not in existing_tns:
                db.add(DeliveryRecord(
                    tracking_number=tn, vehicle_id=vehicle_id, origin=ORIGIN_CITY,
                    destination=destinations.get(tn, ""),
                    district=next((o.district for o in ocr_list if o.tracking_number == tn), ""),
                    node_status=1, node_status_name="分拣装车", active=1))
        db.commit()

    # 创建/更新车辆记录（含路点和速度）
    import json
    total_dist = 0
    wps = req.waypoints or []
    if wps and len(wps) > 1:
        from ..services.delivery_tracking import haversine_km
        for i in range(1, len(wps)):
            total_dist += haversine_km(wps[i-1]["lng"], wps[i-1]["lat"], wps[i]["lng"], wps[i]["lat"])
    total_dist = round(total_dist, 2)

    existing_vehicle = db.query(VehicleRecord).filter(VehicleRecord.vehicle_id == vehicle_id).first()
    if existing_vehicle:
        existing_vehicle.waypoints_json = json.dumps(wps) if wps else ""
        existing_vehicle.speed_kmh = req.speed_kmh
        existing_vehicle.total_distance_km = total_dist
        existing_vehicle.bound_packages = len(bound_tns)
        existing_vehicle.status = "running"
    else:
        db.add(VehicleRecord(
            vehicle_id=vehicle_id, waypoints_json=json.dumps(wps) if wps else "",
            speed_kmh=req.speed_kmh, total_distance_km=total_dist,
            bound_packages=len(bound_tns), status="running"))
    db.commit()

    # 启动车辆位置模拟
    if wps and bound_tns:
        start_vehicle_simulation(vehicle_id, wps, req.speed_kmh)

    return {"code": 200, "message": f"发车成功，{len(bound_tns)}个包裹→{vehicle_id}",
            "data": {"vehicle_id": vehicle_id, "total": len(tns), "bound": len(bound_tns),
                     "total_distance_km": total_dist, "speed_kmh": req.speed_kmh, "results": bind_results}}


# ========== 车辆列表 ==========

@router.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db)):
    vehicles = db.query(VehicleRecord).order_by(VehicleRecord.id.desc()).limit(50).all()
    result = []
    for v in vehicles:
        pkgs = get_vehicle_packages(v.vehicle_id)
        state = get_vehicle_state(v.vehicle_id)
        result.append({
            "vehicle_id": v.vehicle_id, "status": v.status,
            "bound_packages": v.bound_packages or len(pkgs),
            "speed_kmh": v.speed_kmh or (state.get("speed_kmh") if state else 0),
            "total_distance_km": v.total_distance_km or (state.get("total_distance_km") if state else 0),
            "traveled_km": state.get("traveled_km", 0) if state else 0,
            "remaining_km": state.get("remaining_km", 0) if state else 0,
            "eta_minutes": state.get("eta_minutes", 0) if state else 0,
            "progress_percent": state.get("progress_percent", 0) if state else 0,
            "package_count": len(pkgs),
            "created_at": str(getattr(v, "created_at", "")),
            "finished_at": str(v.finished_at) if v.finished_at else "",
            "has_active_deliveries": any(p.get("node_status_code", 0) < 4 for p in pkgs) if pkgs else False,
        })
    return {"code": 200, "message": f"共{len(result)}辆车", "data": result}


# ========== 绑定关系 ==========

@router.get("/bindings")
def bindings(): return {"code": 200, "data": get_binding_summary()}


# ========== 车辆实时状态 ==========

@router.get("/vehicle/{vehicle_id}/status")
def vehicle_status(vehicle_id: str):
    pkgs = get_vehicle_packages(vehicle_id)
    state = get_vehicle_state(vehicle_id)
    if state:
        return {"code": 200, "data": {
            "vehicle_id": vehicle_id, "package_count": len(pkgs), "packages": pkgs,
            **state,
        }}
    return {"code": 200, "data": {"vehicle_id": vehicle_id, "package_count": len(pkgs), "packages": pkgs}}


# ========== 包裹配送追踪（小程序调用） ==========

@router.get("/track/{tracking_number}")
def track_delivery(tracking_number: str):
    """小程序端：根据运单号查询配送状态"""
    from ..services.delivery_tracking import get_package_status
    status = get_package_status(tracking_number)
    if not status:
        return {"code": 404, "message": "未找到该包裹的配送记录"}
    return {"code": 200, "data": status}


# ========== 城市/分区列表 ==========

@router.get("/cities")
def list_cities():
    districts = [{"name": n, "chute": DISTRICT_CHUTE_MAP.get(n, ""),
                  "lng": DISTRICT_COORDS.get(n, (0, 0))[0],
                  "lat": DISTRICT_COORDS.get(n, (0, 0))[1]} for n in sorted(VALID_DISTRICTS)]
    return {"code": 200, "data": {"districts": districts, "count": len(districts)}}


# ========== 分区管理 ==========

class SyncReq(BaseModel):
    from_district: str = Field(default="")
    to_district: str
    tracking_numbers: Optional[list[str]] = Field(default=None)


@router.get("/district-options")
def district_opts():
    opts = [{"name": d, "chute": DISTRICT_CHUTE_MAP.get(d, ""), "is_active": True}
            for d in sorted(VALID_DISTRICTS)]
    return {"code": 200, "data": {"districts": opts, "count": len(opts)}}


@router.get("/district-packages")
def district_pkgs(district: str = Query(""), db: Session = Depends(get_db)):
    r = get_packages_by_district(district, db)
    if not r["valid"]: raise HTTPException(400, r["message"])
    return {"code": 200, "message": r["message"], "data": r["data"]}


@router.get("/district-validate")
def district_validate(db: Session = Depends(get_db)):
    issues = validate_district_consistency(db)
    return {"code": 200, "message": "一致" if issues["is_clean"] else f"发现{issues['total_issues']}个问题",
            "data": issues}


@router.put("/district-sync")
def district_sync(req: SyncReq, db: Session = Depends(get_db)):
    if not req.to_district: raise HTTPException(400, "目标分区不能为空")
    if req.to_district not in VALID_DISTRICTS:
        raise HTTPException(400, f"非法分区，可选: {sorted(VALID_DISTRICTS)}")
    r = sync_district_change(req.from_district, req.to_district, req.tracking_numbers, db)
    if not r["success"]: raise HTTPException(500, r["message"])
    return {"code": 200, "message": r["message"], "data": r}


@router.post("/district-auto-fix")
def district_autofix(db: Session = Depends(get_db)):
    r = auto_fix_consistency(db)
    if not r["success"]: raise HTTPException(500, r["message"])
    return {"code": 200, "message": r["message"], "data": r}
