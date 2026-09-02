# 月经记录助手 · 数据库设计文档

## 1. 概述

- 数据库：**SQLite**，单文件 data/tracker.db；
- 访问方式：Python 标准库 sqlite3，无 ORM、无外部数据库服务；
- 建表：服务启动时由 app/db.py::init_db() 幂等执行（IF NOT EXISTS）；
- 所有查询都带 user_id 条件，数据按用户严格隔离。

## 2. 表结构

### 2.1 users — 用户表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 用户 ID |
| username | TEXT | NOT NULL UNIQUE | 用户名 |
| password_hash | TEXT | NOT NULL | PBKDF2-SHA256 哈希串 |
| created_at | TEXT | DEFAULT 当前时间 | 注册时间 |

password_hash 存储格式：

```text
pbkdf2_sha256$200000$<盐 hex>$<摘要 hex>
```

不存明文密码；盐随机 16 字节，迭代 20 万次。

### 2.2 daily_records — 每日记录表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 记录 ID |
| user_id | INTEGER | NOT NULL, REFERENCES users(id) | 所属用户 |
| date | TEXT | NOT NULL | 日期 YYYY-MM-DD |
| flow | TEXT | NOT NULL DEFAULT 'none' | 经量 |
| colors | TEXT | NOT NULL DEFAULT '[]' | 颜色（JSON 数组） |
| clots | TEXT | NOT NULL DEFAULT 'none' | 血块 |
| pain | TEXT | NOT NULL DEFAULT 'none' | 疼痛程度 |
| symptoms | TEXT | NOT NULL DEFAULT '[]' | 症状（JSON 数组） |
| mood | TEXT | NOT NULL DEFAULT '[]' | 情绪（JSON 数组） |
| medication | TEXT | NOT NULL DEFAULT '' | 用药 |
| notes | TEXT | NOT NULL DEFAULT '' | 备注 |
| created_at | TEXT | DEFAULT 当前时间 | 创建时间 |
| updated_at | TEXT | DEFAULT 当前时间 | 更新时间 |

约束：UNIQUE(user_id, date) —— 每个用户每天最多一条记录，
写入使用 ON CONFLICT DO UPDATE 实现"新增或更新"。

枚举取值（存英文键，前端映射中文文案）：

| 字段 | 取值 |
|---|---|
| flow | none / spotting / light / medium / heavy |
| colors | bright_red / dark_red / pink / brown / black / orange / grey（可多选） |
| clots | none / small / large |
| pain | none / mild / moderate / severe |
| symptoms | bloating / headache / breast_tenderness / nausea / fatigue / diarrhea / constipation / appetite_change / acne / insomnia（可多选） |
| mood | calm / happy / anxious / irritable / sad / tired（可多选） |

colors / symptoms / mood 用 JSON 文本存数组，由代码在读写时序列化/反序列化
（app/routers/records.py 的 row_to_record），存储层简单、读出来即数组。

## 3. 关键设计决策

1. **预测与通知不落库，实时计算。**
   没有 notifications 表：/api/predictions 与 /api/notifications 每次请求时
   从 daily_records 现算。好处是结果永远和最新记录一致，也不存在过期/已读状态管理。
   代价是每次请求要读该用户全部记录——当前数据量下无性能压力。

2. **日期用 TEXT（ISO 格式）而不是日期类型。**
   YYYY-MM-DD 字典序即时间序，排序、区间比较、跨语言传递都直观。

3. **一天一条记录（UNIQUE(user_id, date)）+ upsert。**
   数据结构与"日历上点一天编辑一次"的交互一一对应，避免重复记录。

4. **用户隔离靠"查询恒带 user_id"。**
   外键保证记录必须属于存在的用户；所有 SQL 均以 user_id 过滤，接口层再以
   token 中的用户 id 校验。

5. **无迁移版本机制。**
   v0.1 表结构简单，靠 CREATE TABLE IF NOT EXISTS 幂等建表。
   若将来改表结构，需要手动写迁移（例如加 schema_version 表）。

## 4. 除数据库以外的存储组件

服务器侧只有两个持久化文件，都在 data/ 目录：

| 文件 | 内容 | 是否业务数据 |
|---|---|---|
| data/tracker.db | 全部业务数据（用户、记录） | 是 |
| data/secret.key | 令牌签名密钥（随机 32 字节） | 否，但影响登录态 |

除此之外：

- **没有** Redis、Memcached 等缓存服务；
- **没有** 消息队列、任务调度；
- **没有** 对象存储 / 文件上传；
- 浏览器端 localStorage 只存 token 与用户名，属于客户端本地，迁移服务器无需处理。

结论：**业务数据全部集中在 tracker.db 一个文件里。**

## 5. 迁移服务器要拷贝什么

迁移 = 拷贝项目代码 + 两个持久化文件：

```text
menstrual-tracker/          ← 整个项目目录（代码 + static + requirements.txt）
└── data/
    ├── tracker.db          ← 必须拷（全部业务数据）
    └── secret.key          ← 建议一起拷（保持已登录用户不掉线）
```

具体说明：

- **只拷 tracker.db 也够**：业务数据一条不丢；因为新机器没有 secret.key，
  服务会重新生成一个新密钥，效果是**所有用户需要重新登录**（旧 token 验签失败），
  密码不受影响。
- **不需要拷 .venv/**：在新机器上重新 pip install -r requirements.txt 即可。
- **不要拷 data/ 里的其他临时文件**（当前没有）。

推荐迁移步骤：

```bash
# 1. 旧机器：停服
# 2. 打包（排除 .venv 等）
tar -czf tracker-backup.tar.gz menstrual-tracker --exclude='.venv' --exclude='__pycache__'
# 3. 新机器：解压、装依赖、启动
tar -xzf tracker-backup.tar.gz
cd menstrual-tracker
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 6. 备份建议

- 简单可靠：**停服后直接拷贝 data/tracker.db**（SQLite 单文件，拷完即可归档）；
- 不想停服：用 sqlite3 tracker.db ".backup backup.db"（需要 sqlite3 命令行），
  或写一个 Python sqlite3.Connection.backup() 脚本做在线一致性备份；
- 与 secret.key 一起归档，恢复后登录态不丢失。

## 7. 与"扩展数据库"的关系

若未来数据量或并发上来，需要把 SQLite 换成 PostgreSQL/MySQL 或加 Redis 缓存，
由于所有数据访问都集中在 app/db.py 与两个查询函数中，替换点清晰，
业务逻辑（cycle.py）与前端无需改动。
