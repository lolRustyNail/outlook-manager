# Outlook 批量邮箱管理台

一个适合本地 Docker 部署的 Outlook 邮箱批量管理工具，前端是网页后台，后端使用 FastAPI，数据保存在 SQLite 中。

## 功能特性

- 批量录入 Outlook 账号
- 按分组管理账号、搜索和筛选
- 保存 `password / access_token / refresh_token / client_id / tenant_id`
- 检测账号 token 是否可用、是否具备读取收件箱的权限
- 读取最近邮件并在网页里预览
- 导出 CSV 备份

## 技术栈

- 后端：FastAPI
- 前端：原生 HTML / CSS / JavaScript
- 数据库：SQLite
- 接口：Microsoft Graph
- 部署：Docker / Docker Compose

## 快速启动

### 方式一：Docker

```bash
docker-compose up -d --build
docker-compose logs -f
```

启动后访问：

- 首页：[http://localhost:8000](http://localhost:8000)
- Swagger：[http://localhost:8000/docs](http://localhost:8000/docs)

停止服务：

```bash
docker-compose down
```

### 方式二：本地运行

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 导入格式

默认支持每行一条数据：

```text
email----password----client_id----refresh_token----access_token----group----note
```

也支持带标题行的 CSV 或制表符文本，例如：

```csv
email,password,client_id,refresh_token,access_token,group_name,note
demo01@outlook.com,pass-demo,client-demo,refresh-demo,,销售组,北美线
demo02@outlook.com,,,,access-demo,售后组,备用邮箱
```

## 环境变量

| 变量名 | 说明 | 默认值 |
| --- | --- | --- |
| `DATABASE_URL` | SQLite 连接串 | `sqlite:///./data/outlook_accounts.db` |

## 注意事项

- 这个工具只适用于你自己拥有或已获授权管理的 Outlook 账号。
- 密码字段在当前版本中只做本地归档展示，真正读信依赖 `access_token` 或 `refresh_token`。
- 如果 `refresh_token` 需要自定义 Azure 应用刷新，请同时填写 `client_id`，必要时补充 `client_secret` 和 `tenant_id`。

---

# Outlook Batch Mailbox Manager

A locally deployable Outlook mailbox batch management tool with web frontend, FastAPI backend, and SQLite storage.

## Features

- Batch import Outlook accounts
- Group management, search and filter accounts
- Store `password / access_token / refresh_token / client_id / tenant_id`
- Check token validity and inbox read permissions
- Preview recent emails in browser
- Export CSV backup

## Tech Stack

- Backend: FastAPI
- Frontend: Vanilla HTML / CSS / JavaScript
- Database: SQLite
- API: Microsoft Graph
- Deployment: Docker / Docker Compose

## Quick Start

### Option 1: Docker

```bash
docker-compose up -d --build
docker-compose logs -f
```

Access after startup:

- Home: [http://localhost:8000](http://localhost:8000)
- Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)

Stop service:

```bash
docker-compose down
```

### Option 2: Local Run

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Import Format

Default format (one record per line):

```text
email----password----client_id----refresh_token----access_token----group----note
```

Also supports CSV or tab-separated text with headers:

```csv
email,password,client_id,refresh_token,access_token,group_name,note
demo01@outlook.com,pass-demo,client-demo,refresh-demo,,Sales,North America
demo02@outlook.com,,,,access-demo,Support,Backup
```

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLite connection string | `sqlite:///./data/outlook_accounts.db` |

## Notes

- This tool is only for Outlook accounts you own or have authorization to manage.
- The password field is for local archiving only; actual email reading requires `access_token` or `refresh_token`.
- If your `refresh_token` requires a custom Azure app, also provide `client_id`, and optionally `client_secret` and `tenant_id`.