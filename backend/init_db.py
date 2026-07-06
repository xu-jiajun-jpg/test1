"""数据库初始化脚本 — 创建所有表 + 预置数据"""
import sys
sys.path.insert(0, ".")

from app.database import engine, SessionLocal
from app.models import Base
from app.models.user import User, Role
import bcrypt


def create_tables():
    print("创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("✓ 所有表创建完成")

    tables = Base.metadata.tables
    for name in tables:
        print(f"  - {name}")


def seed_data():
    """预置默认角色和管理员账号"""
    db = SessionLocal()
    try:
        # 默认角色
        roles = [
            Role(code="admin", name="系统管理员", permissions={"all": True}),
            Role(code="supervisor", name="分拣主管", permissions={
                "upload": ["view"], "ocr": ["view"], "dashboard": ["view"],
                "history": ["view", "export"], "exception": ["view", "handle"],
                "chute": ["view"], "operator": ["view"], "config": ["view"],
            }),
            Role(code="operator", name="分拣操作员", permissions={
                "upload": ["upload", "view"], "ocr": ["view"],
                "dashboard": ["view"],
            }),
            Role(code="maintainer", name="运维人员", permissions={
                "alert": ["view", "handle"], "exception": ["view", "handle"],
                "chute": ["view", "edit"], "config": ["view", "edit"],
            }),
        ]
        for role in roles:
            existing = db.query(Role).filter(Role.code == role.code).first()
            if not existing:
                db.add(role)
                print(f"  + 角色: {role.name}")

        # 默认管理员 admin / admin123
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt())
            db.add(User(
                username="admin",
                password_hash=hashed.decode(),
                display_name="系统管理员",
                role="admin",
                is_active=True,
            ))
            print("  + 默认管理员: admin / admin123")

        # 测试操作员
        op = db.query(User).filter(User.username == "operator").first()
        if not op:
            hashed = bcrypt.hashpw("op123".encode(), bcrypt.gensalt())
            db.add(User(
                username="operator",
                password_hash=hashed.decode(),
                display_name="测试操作员",
                role="operator",
                is_active=True,
            ))
            print("  + 测试操作员: operator / op123")

        db.commit()

        # ===== 预置分拣人员（每个分拣口一个操作员）=====
        from app.models.operator import Operator, OperatorChute

        operator_seeds = [
            {"employee_id": "OP001", "name": "张伟", "phone": "13800000001", "chutes": ["CH-001", "CH-002", "CH-005"]},
            {"employee_id": "OP002", "name": "李娜", "phone": "13800000002", "chutes": ["CH-003", "CH-005"]},
            {"employee_id": "OP003", "name": "王强", "phone": "13800000003", "chutes": ["CH-001", "CH-003", "CH-004"]},
            {"employee_id": "OP004", "name": "赵敏", "phone": "13800000004", "chutes": ["CH-002", "CH-004"]},
            {"employee_id": "OP005", "name": "刘洋", "phone": "13800000005", "chutes": ["CH-001", "CH-005", "CH-003"]},
            {"employee_id": "OP006", "name": "陈静", "phone": "13800000006", "chutes": ["CH-006"]},
        ]
        for seed in operator_seeds:
            existing = db.query(Operator).filter(Operator.employee_id == seed["employee_id"]).first()
            if not existing:
                op_obj = Operator(
                    employee_id=seed["employee_id"],
                    name=seed["name"],
                    phone=seed["phone"],
                    status="active",
                )
                db.add(op_obj)
                db.flush()  # 获取 ID
                # 绑定分拣口
                for ch in seed["chutes"]:
                    db.add(OperatorChute(operator_id=op_obj.id, chute_code=ch))
                print(f"  + 操作员: {seed['name']} ({seed['employee_id']}) → {', '.join(seed['chutes'])}")
        db.commit()

        # ===== 建立 User ↔ Operator 关联 =====
        # 把 display_name='测试操作员' 的用户关联到 CH-006 陈静（如存在）
        operator_user = db.query(User).filter(User.username == "operator").first()
        ch006_op = db.query(Operator).filter(Operator.name == "陈静").first()
        if operator_user and ch006_op and not operator_user.operator_id:
            operator_user.operator_id = ch006_op.id
            print(f"  ✓ 已关联 User(operator) → Operator(陈静 CH-006, id={ch006_op.id})")
        # 也尝试关联 admin → 管理员不需要 operator_id，跳过

        # 回填已有 users：查找所有 operator/supervisor 角色用户，通过 display_name 匹配 Operator
        unmatched = []
        for u in db.query(User).filter(User.role.in_(["operator", "supervisor"]), User.operator_id.is_(None)).all():
            op_match = db.query(Operator).filter(
                (Operator.name == u.display_name)
                | (Operator.name == u.username)
            ).first()
            if op_match:
                u.operator_id = op_match.id
            else:
                unmatched.append(u.username)
        if unmatched:
            print(f"  ⚠ 未找到 Operator 匹配的用户: {', '.join(unmatched)}")
        db.commit()

        # 预置分拣口（强制替换为南昌大区，删除旧省份数据）
        from app.models.sorting import SortingChute
        chutes = [
            SortingChute(chute_code="CH-001", name="东湖区分拣口", location="A区-01", capacity=800),
            SortingChute(chute_code="CH-002", name="西湖区分拣口", location="A区-02", capacity=800),
            SortingChute(chute_code="CH-003", name="青云谱分拣口", location="B区-01", capacity=1000),
            SortingChute(chute_code="CH-004", name="青山湖分拣口", location="B区-02", capacity=800),
            SortingChute(chute_code="CH-005", name="新建红谷滩分拣口", location="B区-03", capacity=800),
            SortingChute(chute_code="CH-006", name="异常件暂存口", location="C区-01", capacity=200),
        ]
        # 先清空旧的分拣口（无外键约束，安全删除）
        old_count = db.query(SortingChute).delete()
        db.flush()
        for ch in chutes:
            db.add(ch)
            print(f"  + 分拣口: {ch.name}")
        if old_count:
            print(f"  ✓ 已替换 {old_count} 个旧分拣口（北京/上海等 → 南昌各区）")

        # 预置分拣规则（强制替换为南昌大区规则）
        from app.models.sorting import SortingRule
        rules = [
            SortingRule(rule_id="R-DH", province="江西", city="南昌市", district="东湖区", target_chute="CH-001", priority=1, description="东湖区 → 东湖区分拣口"),
            SortingRule(rule_id="R-XH", province="江西", city="南昌市", district="西湖区", target_chute="CH-002", priority=1, description="西湖区 → 西湖区分拣口"),
            SortingRule(rule_id="R-QYP", province="江西", city="南昌市", district="青云谱区", target_chute="CH-003", priority=1, description="青云谱区 → 青云谱分拣口"),
            SortingRule(rule_id="R-QSH", province="江西", city="南昌市", district="青山湖区", target_chute="CH-004", priority=1, description="青山湖区 → 青山湖分拣口"),
            SortingRule(rule_id="R-XJ", province="江西", city="南昌市", district="新建区", target_chute="CH-005", priority=1, description="新建区 → 新建红谷滩分拣口"),
            SortingRule(rule_id="R-HGT", province="江西", city="南昌市", district="红谷滩区", target_chute="CH-005", priority=1, description="红谷滩区 → 新建红谷滩分拣口"),
        ]
        # 先清空旧规则（旧省份规则如北京/上海等已废弃）
        old_rule_count = db.query(SortingRule).delete()
        db.flush()
        for rule in rules:
            db.add(rule)
            print(f"  + 分拣规则: {rule.description}")
        if old_rule_count:
            print(f"  ✓ 已替换 {old_rule_count} 个旧分拣规则（北京/上海等 → 南昌各区）")

        # 预置告警规则
        from app.models.alert import AlertRule
        alert_rules = [
            AlertRule(rule_name="分拣失败率过高", metric="fail_rate", threshold=5.0, alert_level="warning", cooldown_minutes=30, description="分拣失败率超过5%"),
            AlertRule(rule_name="分拣严重失败", metric="fail_rate", threshold=15.0, alert_level="critical", cooldown_minutes=15, description="分拣失败率超过15%需紧急处理"),
            AlertRule(rule_name="待处理异常过多", metric="pending_exceptions", threshold=10.0, alert_level="warning", cooldown_minutes=60, description="待处理异常包裹超过10个"),
            AlertRule(rule_name="待处理异常严重", metric="pending_exceptions", threshold=30.0, alert_level="critical", cooldown_minutes=30, description="待处理异常包裹超过30个"),
            AlertRule(rule_name="总失败数预警", metric="fail_count", threshold=3.0, alert_level="info", cooldown_minutes=30, description="分拣失败超过3件"),
        ]
        for ar in alert_rules:
            existing = db.query(AlertRule).filter(AlertRule.rule_name == ar.rule_name).first()
            if not existing:
                db.add(ar)
                print(f"  + 告警规则: {ar.rule_name}")

        db.commit()
        print("  ✓ 已替换或创建告警规则")

        # 预置SLA超时配置
        from app.models.sla_config import SlaConfig
        sla_configs = [
            SlaConfig(chute_code="CH-001", chute_name="东湖区分拣口", accept_timeout=10, process_timeout=30, severity="warning", escalation_action="notify_admin", description="正常口SLA: 接收10min/执行30min"),
            SlaConfig(chute_code="CH-002", chute_name="西湖区分拣口", accept_timeout=10, process_timeout=30, severity="warning", escalation_action="notify_admin", description="正常口SLA: 接收10min/执行30min"),
            SlaConfig(chute_code="CH-003", chute_name="青云谱分拣口", accept_timeout=10, process_timeout=30, severity="warning", escalation_action="notify_admin", description="正常口SLA: 接收10min/执行30min"),
            SlaConfig(chute_code="CH-004", chute_name="青山湖分拣口", accept_timeout=10, process_timeout=30, severity="warning", escalation_action="notify_admin", description="正常口SLA: 接收10min/执行30min"),
            SlaConfig(chute_code="CH-005", chute_name="新建红谷滩分拣口", accept_timeout=10, process_timeout=30, severity="warning", escalation_action="notify_admin", description="正常口SLA: 接收10min/执行30min"),
            SlaConfig(chute_code="CH-006", chute_name="异常件暂存口", accept_timeout=20, process_timeout=60, severity="critical", escalation_action="reassign", description="异常口SLA: 接收20min/执行60min"),
        ]
        for sc in sla_configs:
            existing = db.query(SlaConfig).filter(SlaConfig.chute_code == sc.chute_code).first()
            if not existing:
                db.add(sc)
                print(f"  + SLA配置: {sc.chute_name}")
        db.commit()
        print("  ✓ SLA超时配置已创建")

        print("\n✓ 预置数据写入完成")
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("  物流分拣平台 - 数据库初始化")
    print("=" * 50)
    create_tables()
    print()
    seed_data()
    print("\n数据库初始化完成！")
