# 月经记录助手

一个简洁的月经状况记录与提醒工具：月视图日历记录每日情况，基于历史数据预测下次月经与排卵日，并在网页通知栏中提醒。

## 功能

- 用户名 + 密码注册登录（按用户隔离数据）
- 月视图日历，点击任意一天编辑当天的经量、颜色、血块、疼痛、症状、情绪、用药与备注
- 基于最近至多 6 个周期长度的中位数预测下次月经（含波动范围）与排卵日
- 网页端通知栏：月经将至、排卵期将至、月经可能推迟
- 后端为客户端无关的 JSON API，便于以后扩展小程序等形态

> 本工具仅作记录与参考，不构成医疗建议。

## 文档

- [代码设计文档](docs/design.md)：架构、每个代码文件的职责、核心流程
- [数据库设计文档](docs/database.md)：表结构、存储组件与服务器迁移说明

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 http://127.0.0.1:8000 ，注册账号后即可使用。

数据保存在 `data/tracker.db`（SQLite 单文件），登录密钥在 `data/secret.key`；备份这两个文件即可整体迁移。

## 运行测试

```bash
.venv/bin/python -m pytest tests -q
```

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 注册，返回 token |
| POST | `/api/auth/login` | 登录，返回 token |
| GET | `/api/auth/me` | 当前用户信息 |
| GET | `/api/records?month=YYYY-MM` | 某月记录列表 |
| PUT | `/api/records/{date}` | 新增/更新某天记录 |
| DELETE | `/api/records/{date}` | 删除某天记录 |
| GET | `/api/predictions` | 下次月经与排卵日预测 |
| GET | `/api/notifications` | 通知栏条目 |

除注册登录外，所有接口需在请求头携带 `Authorization: Bearer <token>`。

## 项目结构

```text
app/
  main.py      应用入口
  db.py        SQLite 连接与建表
  auth.py      密码哈希与签名令牌
  cycle.py     周期预测纯函数（可独立测试）
  routers/     认证、记录、预测通知路由
static/        前端页面（无构建步骤）
tests/         预测逻辑单元测试
```

## 扩展方向

- 小程序 / 桌面端：直接复用现有 API，替换前端即可
- 周视图等更多日历形态：只改前端渲染层
- 云端部署：后端无本地状态依赖（除 SQLite 文件），把 `data/` 挂到持久卷即可
- 更大规模或更高并发时，可把会话缓存等迁到 Redis，业务代码无需改动
