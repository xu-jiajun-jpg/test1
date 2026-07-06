"""
数据库迁移脚本：新增 users.operator_id 字段 + 回填关联数据

用法: python backend/migration_add_operator_id.py
"""
import sys
sys.path.insert(0, "backend")

from app.database import engine, SessionLocal
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session


def migration():
    db = SessionLocal()
    try:
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("users")]

        # 1. 添加 operator_id 列
        if "operator_id" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN operator_id INT NULL"))
            print("✓ 已添加 users.operator_id 列")
        else:
            print("• users.operator_id 列已存在，跳过")

        # 2. 回填：通过 display_name 模糊匹配已有 Operator 记录
        #   User.display_name = "张伟(早班分拣员)", Operator.name = "张伟"
        result = db.execute(text("""
            UPDATE users u
            SET u.operator_id = (
                SELECT o.id FROM operators o
                WHERE INSTR(u.display_name, o.name) > 0
                ORDER BY LENGTH(o.name) DESC
                LIMIT 1
            )
            WHERE u.role IN ('operator', 'supervisor')
              AND u.operator_id IS NULL
        """))
        affected = result.rowcount
        print(f"✓ 已回填 {affected} 条 User-Operator 关联")

        # 3. 检查仍未匹配的操作员用户
        unmatched = db.execute(text("""
            SELECT u.id, u.username, u.display_name
            FROM users u
            WHERE u.role IN ('operator', 'supervisor')
              AND u.operator_id IS NULL
        """)).fetchall()
        if unmatched:
            print(f"⚠ 以下 {len(unmatched)} 个操作员用户未找到 Operator 匹配：")
            for u in unmatched:
                print(f"   ID={u[0]}, username={u[1]}, display_name={u[2]}")
        else:
            print("✓ 所有操作员用户均已关联 Operator")

        db.commit()
        print("\n迁移完成！建议重新登录以获取更新后的 JWT Token。")
    finally:
        db.close()


if __name__ == "__main__":
    migration()
