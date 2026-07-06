# 📦 物流分拣平台 v1.0

基于图像识别的智能物流分拣与配送管理系统。

## 快速启动

### 1. 后端
```bash
cd backend
pip install -r requirements.txt
python init_db.py              # 首次运行初始化数据库
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

### 2. 前端
```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

### 3. 包裹追踪小程序
```bash
cd miniapp-standalone
python -m http.server 8081     # http://localhost:8081
```

也可双击项目根目录 `start.bat` 一键启动全部。

## 默认账号

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | 管理员 |
| zhangwei / lina / wangqiang / zhaomin / liuyang / chenjing | op123 | 分拣员 |

## 操作员分拣口

| 工号 | 姓名 | 分拣口 |
|------|------|--------|
| OP001 | 张伟 | CH-001, CH-002, CH-005 |
| OP002 | 李娜 | CH-003, CH-005 |
| OP003 | 王强 | CH-001, CH-003, CH-004 |
| OP004 | 赵敏 | CH-002, CH-004 |
| OP005 | 刘洋 | CH-001, CH-005, CH-003 |
| OP006 | 陈静 | CH-006（异常口,1:1） |

## 端口

| 服务 | 端口 |
|------|------|
| 后端 API | 8003 |
| 前端页面 | 5173 |
| 小程序 | 8081 |

---

## 核心流程

```
上传包裹 → OCR识别 → 智能分拣(CH-001~006) → 操作员处理
→ 申请发车 → 蚁群路径规划 → 管理员审批 → 车辆模拟配送
→ 小程序追踪(进度/ETA/节点)
```

## 项目结构

```
├── backend/          FastAPI 后端
│   ├── app/main.py          入口
│   ├── app/routers/         API 路由
│   ├── app/services/        业务逻辑（分拣/路径/追踪/装箱）
│   ├── app/models/          ORM 模型
│   └── init_db.py           数据库初始化
├── frontend/         Vue3 前端
│   └── src/views/           页面组件
├── miniapp-standalone/  包裹追踪小程序
│   └── index.html
├── start.bat         一键启动
└── README.md
```

## 快速测试

登录管理员 → 上传与识别 → 点击「一键生成模拟包裹」→ 自动识别分拣 → 切换操作员 → 处理任务 → 申请发车 → 管理员审批 → 发车！

---

*2026-07*
