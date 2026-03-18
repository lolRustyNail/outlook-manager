# Outlook Batch Mailbox Manager

English | [简体中文](./README.md)

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