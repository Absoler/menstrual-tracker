# 月经记录助手 · 代码设计文档

> 对应实现版本：v0.1.0（2026-09）

## 1. 项目定位与当前功能

一个"月经状况记录 + 周期提醒"工具。用户注册登录后，在月视图日历上点击任意一天，
记录当天的月经情况；系统基于历史记录预测下次月经与排卵日，并在网页通知栏中提醒。

当前已实现的功能：

- 用户名 + 密码注册登录，数据按用户隔离
- 月视图日历：点击任意日期编辑当天记录（经量、颜色、血块、疼痛、症状、情绪、用药、备注）
- 预测：下次月经日期（含 ± 波动范围）、排卵日
- 通知栏：月经将至、排卵期将至、月经可能推迟、数据积累中
- 客户端无关的 JSON API，前端为无构建步骤的静态单页

## 2. 技术栈与设计原则

| 部分 | 选型 | 说明 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI + Uvicorn | 类型标注自动校验，代码量少、可读性好 |
| 数据库 | SQLite（Python 标准库 sqlite3） | 单文件、零运维，无 ORM |
| 密码存储 | hashlib.pbkdf2_hmac（内置） | 不引入额外依赖 |
| 登录态 | HMAC-SHA256 签名令牌（自实现） | 服务端无会话表 |
| 前端 | 原生 HTML/CSS/JS 单页 | 无构建工具链 |
| 测试 | pytest（单元）+ 冒烟脚本 | 纯函数可独立测试 |

两条设计原则的落实方式：

1. **第一目标：代码简洁易懂**
   - 不用 ORM、不用前端框架、不引构建工具，运行依赖只有 3 个；
   - 预测逻辑做成不依赖框架和数据库的纯函数，读起来就是算法本身；
   - 每个模块职责单一，函数短小。
2. **第二目标：可扩展**
   - 后端只提供 JSON API，与页面形态解耦，小程序可直接复用；
   - 日历渲染与数据层分离，周视图等新视图只改前端；
   - 预测、通知为独立纯函数，可单独测试或替换算法。

## 3. 系统架构

```text
浏览器（登录/日历/编辑弹窗/通知栏）
        │  HTTP + JSON
        ▼
FastAPI 应用（app/main.py）
  ├─ /api/auth/*       注册登录        → app/routers/auth.py
  ├─ /api/records/*    每日记录        → app/routers/records.py
  ├─ /api/predictions  预测            → app/routers/notify.py
  ├─ /api/notifications 通知           → app/routers/notify.py
  └─ /                 静态前端        → static/
        │
        ▼
SQLite（data/tracker.db）── 数据访问统一走 app/db.py
```

## 4. 目录结构

```text
menstrual-tracker/
├── app/                  # 后端 Python 包
│   ├── main.py           # 应用入口
│   ├── db.py             # 数据库连接与建表
│   ├── auth.py           # 密码哈希、令牌签发与校验
│   ├── cycle.py          # 周期预测纯函数
│   └── routers/          # API 路由
│       ├── auth.py
│       ├── records.py
│       └── notify.py
├── static/               # 前端（无构建）
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tests/                # 单元测试
│   └── test_cycle.py
├── scripts/              # 辅助脚本
│   └── smoke_api.py      # API 冒烟测试
├── data/                 # 运行时生成（.gitignore 忽略）
│   ├── tracker.db
│   └── secret.key
├── docs/                 # 文档
├── requirements.txt
└── README.md
```

## 5. 文件级说明

### app/main.py — 应用入口

创建 FastAPI 实例，通过 lifespan 在启动时调用 db.init_db() 建表，
挂载三个路由（auth / records / notify），最后把 / 挂到 static/ 目录
（html=True 使访问根路径时直接返回 index.html）。

路由注册先于静态挂载，因此 /api/* 请求不会落到静态文件处理。

### app/db.py — 数据库访问

- DATA_DIR / DB_PATH：固定到项目根目录下的 data/tracker.db；
- SCHEMA：建表 SQL（users、daily_records），字段见数据库设计文档；
- get_db()：返回行式连接（sqlite3.Row），开启外键约束；
  配合 with 语句使用，正常退出自动提交、异常自动回滚；
- init_db()：确保目录存在并执行建表 SQL（幂等，IF NOT EXISTS）。

### app/auth.py — 密码与令牌

- hash_password() / verify_password()：PBKDF2-SHA256（20 万次迭代、16 字节随机盐），
  存储格式 pbkdf2_sha256$迭代次数$盐hex$摘要hex，比较用 hmac.compare_digest 防时序攻击；
- create_token() / decode_token()：自实现的签名令牌，结构为
  Base64URL(载荷).Base64URL(HMAC-SHA256(载荷))，载荷含用户 id、用户名、30 天过期时间；
- get_current_user()：FastAPI 依赖，解析 Authorization: Bearer <token>，
  校验签名与过期时间后返回 {"id", "username"}，失败抛 401。

> 说明：令牌是"签名但未加密"的，载荷里只有用户 id/用户名/过期时间，不含敏感信息，够用且简单。

### app/cycle.py — 预测核心（纯函数）

不依赖 Web 框架与数据库，是算法与业务逻辑所在，也是单元测试的主要对象：

- FLOW_VALUES / LEAD_DAYS：枚举与提醒提前天数（3 天）；
- is_period_day(record)：经量非 none 即视为有经血（点滴及以上）；
- period_starts(records)：按日期排序后识别每次经期首日；
  与上一个经期日间隔 >1 天时视为新一次经期（连续天数算同一次）；
- cycle_lengths(starts)：相邻首日间隔天数，过滤 <10 天的异常值；
- predict(starts, max_cycles=6)：
  - 不足 2 次经期记录 → insufficient，不硬猜；
  - 取最近至多 6 个周期长度的中位数（四舍五入）作为周期天数；
  - 下次月经 = 最近一次首日 + 中位数；波动范围 = 周期长度标准差（至少 1 天）；
  - 排卵日 = 下次月经 − 14 天（黄体期约 14 天的医学近似）；
- build_notifications(pred, today, period_started)：
  - 数据不足 → 一条 info；
  - 月经在 3 天内 → period；超过预测日 + 波动范围仍未记录新经期 → late；
  - 排卵日在 3 天内 → ovulation。

### app/routers/auth.py — 认证路由

- POST /api/auth/register：校验用户名（3-32 字符）与密码（至少 6 位），
  查重后写入用户并返回 token；
- POST /api/auth/login：校验密码，返回 token；
- GET /api/auth/me：返回当前用户（用于前端启动时恢复登录态）。

### app/routers/records.py — 每日记录路由

- 定义各枚举常量（颜色、血块、疼痛、症状、情绪）与 RecordIn 请求模型；
- _validate()：对经量/颜色/血块/疼痛/症状/情绪做白名单校验，非法值返回 422；
- GET /api/records?month=YYYY-MM：按用户 + 月份区间查询，返回该月全部记录；
- PUT /api/records/{date}：新增或更新某天记录，SQL 用
  ON CONFLICT(user_id, date) DO UPDATE 实现一天一条的 upsert；
- DELETE /api/records/{date}：删除某天记录；
- row_to_record()：把库里的 JSON 文本字段解析回数组，屏蔽存储细节。

### app/routers/notify.py — 预测与通知路由

- 内部 _records(user_id)：读出某用户全部记录；
- GET /api/predictions：period_starts → predict 返回预测结果；
- GET /api/notifications：计算预测，并判断预测的经期日后是否已记录新经期
  （period_started），生成通知列表。

### static/ — 前端

- index.html：页面骨架。三个视图区块：登录/注册表单、主界面（通知栏 + 侧栏 + 日历）、
  日期编辑弹窗；
- app.js：全部前端逻辑。
  - OPTIONS：字段取值与中文文案的映射表（与后端枚举一致）；
  - api()：fetch 封装，自动带 Authorization 头与 JSON 解析；
  - 登录/注册表单切换与提交；
  - renderCalendar()：月历渲染（周一起始，含上月/下月补位、今天高亮、
    有经量的日期按量级着色）；
  - 编辑弹窗：按 OPTIONS 动态生成表单（下拉 + 多选 chips），保存走 PUT、
    删除走 DELETE，成功后刷新日历、预测与通知；
  - renderSummary()：展示下次月经、排卵日与数据说明；
  - renderNotifications()：通知栏渲染，可逐条关闭；
  - token 与用户名存 localStorage，启动时用 /api/auth/me 恢复登录态。
- style.css：整体样式（浅色主题、日历网格、通知栏左色条、响应式布局）。

### tests/test_cycle.py — 单元测试

只测 cycle.py 纯函数，固定日期、无数据库无网络。7 个用例覆盖：
经期首日识别、中位数预测、数据不足兜底、月经/排卵/逾期/数据积累四类通知。

### scripts/smoke_api.py — API 冒烟测试

假定服务已启动，用标准库 urllib 按真实 HTTP 流程验证：注册、登录、当前用户、
写入与按月读取记录、预测数值（2026-09-01 / 2026-08-18）、通知接口、
用户数据隔离、错误密码拒绝、静态首页。任一步失败则退出码非 0。

### requirements.txt / README.md

- requirements.txt：仅 3 个运行/测试依赖；
- README.md：快速开始、API 概览、扩展方向。

## 6. 核心流程

### 6.1 认证流程

注册/登录成功后签发 token（含 30 天有效期）→ 前端存 localStorage →
后续每个请求带 Authorization: Bearer <token> → 服务端 get_current_user
验签、查过期 → 路由里用返回的 user 作为当前用户。

### 6.2 记录读写流程

点击日历某天 → 前端 openEditor() 生成表单 → 保存时 PUT /api/records/{date} →
服务端校验枚举与日期 → upsert 到 daily_records → 前端更新本地 Map 并重渲染日历。

### 6.3 预测与通知流程

```text
daily_records(该用户全部)
  → period_starts() 识别经期首日
  → cycle_lengths() 周期长度
  → predict() 中位数 → 下次月经、排卵日、波动范围
  → build_notifications() 生成通知栏条目
```

预测与通知**每次请求时实时计算**，不落库，因此永远与最新记录一致。

## 7. 测试策略

- **单元测试（pytest）**：覆盖 cycle.py 的全部行为，跑得快（<1 秒）、结果确定；
- **冒烟测试（smoke_api.py）**：验证真实 HTTP 全链路，作为部署前的快速体检；
- 手动验证：浏览器打开根路径注册账号，点日历编辑、切月、查看预测与通知。

## 8. 已知边界与扩展点

- 预测是统计近似，个体差异大，界面已注明"仅供参考"；
- 通知是网页站内通知，无系统推送/邮件；将来可扩展推送渠道而不改核心算法；
- SQLite 适合单机/低并发；上云后可保持 SQLite（挂持久卷）或换 Redis/Postgres，
  因数据访问集中在 db.py，替换面可控；
- 数据库无版本迁移机制，结构变更时需要手动处理（可在后续加 schema_version）。
