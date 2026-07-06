# 📦 物流分拣平台 v1.0

基于图像识别（OCR + 条码）的智能物流分拣与配送管理系统。支持包裹上传识别、自动分拣决策、操作员任务派发、蚁群路径规划、车辆模拟配送、实时大屏监控等完整物流链路。

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | **FastAPI** (Python 3.x) | RESTful API + WebSocket 实时推送 |
| ORM | **SQLAlchemy 2.0** | 数据模型与数据库操作 |
| OCR 引擎 | **PaddleOCR** | 运单面单文字识别 |
| 条码识别 | **pyzbar** | 条形码 / 二维码解码 |
| 图像处理 | **OpenCV + Pillow** | 图像预处理、破损检测、模拟生成 |
| 前端框架 | **Vue 3** (`<script setup>`) | 响应式 SPA |
| UI 组件库 | **Element Plus** | 企业级 UI 组件 |
| 图表 | **ECharts 6** | 大屏数据可视化 |
| 状态管理 | **Pinia** | 认证 / 大屏 / 任务状态 |
| 构建工具 | **Vue CLI 5** | 开发与打包 |
| 数据库 | **MySQL 8.x** | 关系型数据持久化 |
| 地图 | **Leaflet** | 配送路径可视化 |

## 快速启动

### 前置条件

- Python 3.10+（需安装 pip）
- Node.js 16+（需安装 npm）
- MySQL 8.x（需运行在 `localhost:3306`，账号 `root` 密码 `123456`）

### 1. 后端

```bash
cd backend
pip install -r requirements.txt   # 安装依赖（首次较慢，含 PaddleOCR）
python init_db.py                 # 首次运行：创建数据库表 + 预置数据
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

### 2. 前端

```bash
cd frontend
npm install
npm run serve                     # http://localhost:8080
```

### 3. 包裹追踪小程序

```bash
cd miniapp-standalone
python -m http.server 8081        # http://localhost:8081
```

### 一键启动

双击项目根目录 `start.bat`，自动打开三个服务窗口。

## 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 管理端 | http://localhost:8080 | 管理员 / 操作员双端登录 |
| 包裹追踪 | http://localhost:8081 | 用户查询包裹状态 |
| API 文档 (Swagger) | http://localhost:8003/docs | 在线接口调试 |
| API 文档 (ReDoc) | http://localhost:8003/redoc | 备用文档风格 |

## 默认账号

### 管理端

| 账号 | 密码 | 角色 | 权限范围 |
|------|------|------|----------|
| `admin` | `admin123` | 系统管理员 | 全部功能 |
| `zhangwei` | `op123` | 分拣员 (OP001 张伟) | 操作员端 |
| `lina` | `op123` | 分拣员 (OP002 李娜) | 操作员端 |
| `wangqiang` | `op123` | 分拣员 (OP003 王强) | 操作员端 |
| `zhaomin` | `op123` | 分拣员 (OP004 赵敏) | 操作员端 |
| `liuyang` | `op123` | 分拣员 (OP005 刘洋) | 操作员端 |
| `chenjing` | `op123` | 分拣员 (OP006 陈静) | 操作员端（CH-006 异常口） |

## 核心业务流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 上传包裹  │───→│ OCR 识别  │───→│ 智能分拣  │───→│ 任务派发  │───→│ 操作员处理 │
│ (图片/模拟)│    │(PaddleOCR)│    │(CH-001~6)│    │(WebSocket)│    │(接收/完成)│
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └─────┬────┘
                                                                       │
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│ 小程序追踪 │←───│ 车辆模拟  │←───│ 管理员审批 │←───│ 申请发车  │←─────────┘
│(进度/ETA) │    │(Leaflet) │    │          │    │(3D装箱)  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 任务生命周期（9 态状态机）

```
pending → dispatched → accepted → processing → completed → verified
                ↓           ↓           ↓
             rejected     stale      failed (异常暂停)
```

## 分拣口与操作员

| 分拣口 | 名称 | 负责区域 | 操作员 |
|--------|------|----------|--------|
| CH-001 | 东湖区分拣口 | 东湖区 | 张伟、王强、刘洋 |
| CH-002 | 西湖区分拣口 | 西湖区 | 张伟、赵敏 |
| CH-003 | 青云谱分拣口 | 青云谱区 | 李娜、王强、刘洋 |
| CH-004 | 青山湖分拣口 | 青山湖区 | 王强、赵敏 |
| CH-005 | 新建红谷滩分拣口 | 新建区 / 红谷滩区 | 张伟、李娜、刘洋 |
| CH-006 | 异常件暂存口 | 异常包裹专用 | 陈静（1:1） |

## 项目结构

```
├── backend/                          # FastAPI 后端
│   ├── app/
│   │   ├── main.py                   # 应用入口 (CORS/静态挂载/lifespan)
│   │   ├── config.py                 # 全局配置 (数据库/JWT/上传)
│   │   ├── database.py               # SQLAlchemy 连接与会话
│   │   ├── routers/                  # API 路由 (25个模块)
│   │   │   ├── auth.py               # 认证登录
│   │   │   ├── upload.py             # 图片上传
│   │   │   ├── ocr.py                # OCR 识别
│   │   │   ├── barcode.py            # 条码识别
│   │   │   ├── sorting.py            # 分拣决策
│   │   │   ├── dashboard.py          # 实时大屏
│   │   │   ├── exception_router.py   # 破损检测与异常
│   │   │   ├── chute.py              # 分拣口管理
│   │   │   ├── operator_router.py    # 人员管理
│   │   │   ├── system_config.py      # 系统配置
│   │   │   ├── export.py             # 数据导出
│   │   │   ├── alert_router.py       # 告警管理
│   │   │   ├── user_mgmt.py          # 用户权限
│   │   │   ├── track.py              # 包裹追踪
│   │   │   ├── scheduling.py         # 智能排班
│   │   │   ├── optimization.py       # 路径优化
│   │   │   ├── remote_ops_router.py  # 远程运维
│   │   │   ├── demo.py               # 演示模式 + 设备对接
│   │   │   ├── logistics.py          # 物流配送管理
│   │   │   ├── message_router.py     # 消息中心
│   │   │   ├── task_dispatch.py      # 任务派发
│   │   │   ├── task_accept.py        # 任务接收执行
│   │   │   ├── task_monitor.py       # 任务监控
│   │   │   └── sla_config_router.py  # SLA 配置
│   │   ├── services/                 # 业务逻辑层 (18个服务)
│   │   │   ├── sim_generator.py      # 模拟包裹图片生成
│   │   │   ├── ocr_service.py        # PaddleOCR 封装
│   │   │   ├── barcode_service.py    # 条码解码
│   │   │   ├── sort_engine.py        # 分拣规则引擎
│   │   │   ├── damage_detector.py    # 破损检测
│   │   │   ├── load_packer.py        # 3D 装箱算法
│   │   │   ├── aco_planner.py        # 蚁群路径规划
│   │   │   ├── route_optimizer.py    # 路径优化 (遗传+蚁群)
│   │   │   ├── vehicle_sim.py        # 车辆行驶模拟
│   │   │   ├── delivery_tracking.py  # 配送轨迹追踪
│   │   │   ├── scheduling_engine.py  # AI 预测排班
│   │   │   ├── sla_monitor.py        # SLA 超时监控
│   │   │   ├── data_cleanup.py       # 数据清理
│   │   │   └── ...
│   │   ├── models/                   # ORM 数据模型 (23张表)
│   │   ├── middleware/               # 认证中间件
│   │   └── websocket/                # WebSocket 管理 (分组广播)
│   ├── uploads/                      # 上传文件存储
│   └── init_db.py                    # 数据库初始化 + 预置数据
│
├── frontend/                         # Vue 3 前端
│   └── src/
│       ├── views/                    # 页面组件 (21个)
│       │   ├── Dashboard.vue         # 实时大屏
│       │   ├── Upload.vue            # 图片上传
│       │   ├── OcrResult.vue         # 识别结果 + 模拟生成
│       │   ├── History.vue           # 历史记录
│       │   ├── ExceptionList.vue     # 异常列表
│       │   ├── ChuteManage.vue       # 分拣口管理
│       │   ├── OperatorManage.vue    # 人员管理
│       │   ├── SystemConfig.vue      # 系统配置
│       │   ├── AlertManage.vue       # 告警管理
│       │   ├── UserManage.vue        # 用户管理
│       │   ├── TrackQuery.vue        # 包裹追踪
│       │   ├── MessageCenter.vue     # 消息中心
│       │   ├── Scheduling.vue        # 智能排班
│       │   ├── Logistics.vue         # 路径优化与物流
│       │   ├── RemoteOps.vue         # 远程运维
│       │   ├── Optimization.vue      # 优化参数
│       │   ├── OperatorTasks.vue     # 操作员任务
│       │   ├── OperatorLogistics.vue # 操作员物流
│       │   ├── OperatorException.vue # 操作员异常处理
│       │   └── Login.vue             # 登录页
│       ├── components/               # 公共组件
│       ├── api/                      # API 请求封装
│       ├── store/                    # Pinia 状态管理
│       ├── router/                   # Vue Router 路由
│       └── utils/                    # WebSocket 工具
│
├── miniapp-standalone/               # 包裹追踪小程序
│   └── index.html                    # 独立单页应用
│
├── start.bat                         # Windows 一键启动脚本
├── .gitignore
└── README.md
```

## API 模块一览

| 模块 | 前缀 | 说明 |
|------|------|------|
| 认证 | `/api/auth` | 登录 / 注册 / Token |
| 上传 | `/api/upload` | 图片上传管理 |
| OCR | `/api/ocr` | 运单文字识别 |
| 条码 | `/api/barcode` | 条码解码与查询 |
| 分拣 | `/api/sort` | 分拣规则与决策 |
| 大屏 | `/api/stats` | 实时统计 + WebSocket |
| 异常 | `/api/exceptions` | 破损检测 + 异常处理 |
| 分拣口 | `/api/chutes` | 分拣口 CRUD |
| 人员 | `/api/operators` | 分拣人员管理 |
| 配置 | `/api/config` | 系统参数配置 |
| 导出 | `/api/export` | Excel / PDF 导出 |
| 告警 | `/api/alerts` | 告警规则与历史 |
| 用户 | `/api/users` | 用户权限管理 |
| 追踪 | `/api/track` | 包裹状态查询 |
| 排班 | `/api/scheduling` | AI 预测 + 排班计划 |
| 优化 | `/api/optimization` | 路径 + 装载优化 |
| 运维 | `/api/ops` | 设备监控 / 多中心 |
| 演示 | `/api/demo` | 模拟包裹一键生成 |
| 设备 | `/api/device` | 相机 / 扫码枪对接 |
| 物流 | `/api/logistics` | 装箱 / 发车 / 追踪 |
| 消息 | `/api/messages` | 管理员-操作员消息 |
| 任务 | `/api/tasks` | 派发 / 接收 / 监控 |
| SLA | `/api/sla-config` | 超时阈值配置 |

## 核心功能详解

### 1. 模拟包裹生成
在「识别结果」页面可一键生成模拟包裹（1-40张），支持控制破损占比。系统自动生成包含收件人、地址、条码的仿真运单面单图片，并后台走通完整 OCR → 分拣链路。

### 2. 智能分拣引擎
基于规则的分拣引擎，自动将南昌 6 大行政区的包裹分配到对应分拣口。非南昌目的地自动标记为需人工复核。集成完整性检测、去重校验、破损叠加。

### 3. 任务派发协同
管理员可主动派发 / 催办 / 改派任务，操作员通过专属端接收、执行、完成或上报异常。全程 WebSocket 实时推送状态变更，支持 SLA 超时告警。

### 4. 路径规划与配送
- **3D 装箱**：First Fit Decreasing Height 算法，自动计算最优装载方案
- **蚁群算法**：南昌本地多分区最短路径规划
- **车辆模拟**：沿规划路径匀速行驶，实时计算位置与 ETA
- **Leaflet 地图**：配送路线可视化展示

### 5. 实时大屏
Dashboard 通过 WebSocket 实时接收分拣统计、告警事件、任务状态变更。ECharts 图表展示分拣口负载、成功率趋势、异常分布等关键指标。

### 6. 破损检测
基于 OpenCV 的图像分析，自动检测包裹是否存在破损、变形、渗漏、污渍等异常，并生成异常记录进入 CH-006 异常处理流程。

## 快速测试

```
1. 登录管理员 → admin / admin123
2. 进入「识别结果」→ 设置数量和破损占比 → 点击「一键生成模拟包裹」
3. 等待后台 OCR 识别 + 自动分拣完成（刷新列表查看）
4. 切换操作员账号登录（如 zhangwei / op123）
5. 进入操作员端「任务列表」→ 接收并处理分拣任务
6. 进入操作员端「物流配送」→ 申请发车
7. 切回管理员 → 进入「路径优化」→ 审批发车
8. 在小程序 http://localhost:8081 输入运单号查询追踪进度
```

## 端口

| 服务 | 端口 |
|------|------|
| 后端 API | 8003 |
| 前端页面 | 8080 |
| 小程序 | 8081 |

## 数据库

- 数据库类型：MySQL 8.x
- 数据库名：`sorting_platform`
- 默认连接：`root:123456@localhost:3306/sorting_platform`
- 数据表：23 张（users, roles, upload_records, ocr_results, barcode_results, sorting_rules, sorting_decisions, sorting_chutes, operators, operator_chutes, exception_records, alert_rules, alert_history, configs, config_history, daily_stats, export_records, audit_logs, vehicle_records, delivery_records, task_assignments, sla_config, message_records）
- 初始化：运行 `python init_db.py` 自动建表 + 预置数据

## 环境变量（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_USER` | `root` | 数据库用户名 |
| `DB_PASSWORD` | `123456` | 数据库密码 |
| `DB_HOST` | `localhost` | 数据库地址 |
| `DB_PORT` | `3306` | 数据库端口 |
| `DB_NAME` | `sorting_platform` | 数据库名 |
| `SECRET_KEY` | `sort-platform-secret-key-2026` | JWT 密钥 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 地址（可选） |

---

*物流分拣平台 v1.0 — 2026-07*
