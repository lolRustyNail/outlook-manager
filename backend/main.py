from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import get_db, init_db
from models import Account
from outlook_service import GraphApiError, OutlookService
from schemas import (
    AccountCreate,
    AccountDetail,
    AccountListItem,
    AccountUpdate,
    BatchIdsRequest,
    CheckResult,
    EmailListResponse,
    ImportTextRequest,
    OverviewResponse,
    TokenPayload,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES_DIR = FRONTEND_DIR / "templates"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Outlook 邮箱管理台", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def normalize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_group_name(value: Optional[str]) -> str:
    cleaned = normalize_optional(value)
    if cleaned in (None, "", "Default", "default"):
        return "默认分组"
    return cleaned


def get_account_or_404(db: Session, account_id: int) -> Account:
    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return account


def derive_auth_mode(account: Account) -> str:
    if account.refresh_token and account.access_token:
        return "refresh+access"
    if account.refresh_token:
        return "refresh_token"
    if account.access_token:
        return "access_token"
    if account.password:
        return "password_archive"
    return "manual_token"


def seed_status(account: Account) -> None:
    account.auth_mode = derive_auth_mode(account)
    has_token = bool(account.access_token or account.refresh_token)

    if has_token and account.status in (None, "", "needs_token"):
        account.status = "pending"
        account.status_message = "凭据已保存，等待在线检测"
    elif not has_token:
        account.status = "needs_token"
        account.status_message = "暂未提供 access_token 或 refresh_token"


def account_to_list_item(account: Account) -> AccountListItem:
    return AccountListItem(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        password=account.password,
        group_name=normalize_group_name(account.group_name),
        auth_mode=account.auth_mode,
        is_active=account.is_active,
        status=account.status,
        status_message=account.status_message,
        has_password=bool(account.password),
        has_access_token=bool(account.access_token),
        has_refresh_token=bool(account.refresh_token),
        token_expires_at=account.token_expires_at,
        last_check_at=account.last_check_at,
        last_sync_at=account.last_sync_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def account_to_detail(account: Account) -> AccountDetail:
    item = account_to_list_item(account)
    return AccountDetail(
        **item.model_dump(),
        note=account.note,
        client_id=account.client_id,
        client_secret=account.client_secret,
        tenant_id=account.tenant_id,
        access_token=account.access_token,
        refresh_token=account.refresh_token,
    )


def apply_account_values(account: Account, values: Dict[str, Any], allow_blank_clear: bool = True) -> None:
    clearable_fields = {
        "display_name",
        "group_name",
        "password",
        "note",
        "client_id",
        "client_secret",
        "tenant_id",
        "access_token",
        "refresh_token",
    }

    for key, value in values.items():
        if key == "email" and value is not None:
            account.email = value
            continue

        if key == "token_expires_at":
            account.token_expires_at = value
            continue

        if key == "is_active":
            account.is_active = bool(value)
            continue

        if key in clearable_fields:
            cleaned = normalize_optional(value)
            if cleaned is not None or allow_blank_clear:
                setattr(account, key, cleaned)

    account.group_name = normalize_group_name(account.group_name)

    seed_status(account)


def parse_import_rows(raw_text: str) -> tuple[list[dict[str, str]], list[str]]:
    if not raw_text.strip():
        return [], ["导入内容不能为空"]

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return [], ["导入内容不能为空"]

    delimiter = None
    for candidate in ("----", "\t", ",", "|"):
        if candidate in lines[0]:
            delimiter = candidate
            break
    if delimiter is None:
        delimiter = "----"

    order = ["email", "password", "client_id", "refresh_token", "access_token", "group_name", "note"]
    header_alias = {
        "email": "email",
        "mail": "email",
        "username": "email",
        "password": "password",
        "clientid": "client_id",
        "client_id": "client_id",
        "clientsecret": "client_secret",
        "client_secret": "client_secret",
        "tenantid": "tenant_id",
        "tenant_id": "tenant_id",
        "accesstoken": "access_token",
        "access_token": "access_token",
        "refreshtoken": "refresh_token",
        "refresh_token": "refresh_token",
        "group": "group_name",
        "group_name": "group_name",
        "note": "note",
        "displayname": "display_name",
        "display_name": "display_name",
    }

    def normalize_header(value: str) -> str:
        return value.strip().lower().replace(" ", "").replace("-", "").replace(".", "")

    header_map: Optional[list[Optional[str]]] = None
    first_cells = [cell.strip() for cell in lines[0].split(delimiter)]
    if any(normalize_header(cell) in header_alias for cell in first_cells):
        header_map = [header_alias.get(normalize_header(cell)) for cell in first_cells]
        data_lines = lines[1:]
        line_offset = 2
    else:
        data_lines = lines
        line_offset = 1

    rows: list[dict[str, str]] = []
    errors: list[str] = []

    for idx, line in enumerate(data_lines, start=line_offset):
        if line.startswith("#"):
            continue
        cells = [cell.strip() for cell in line.split(delimiter)]
        row: dict[str, str] = {}

        if header_map is not None:
            for position, field_name in enumerate(header_map):
                if field_name and position < len(cells):
                    row[field_name] = cells[position]
        else:
            for position, field_name in enumerate(order):
                if position < len(cells):
                    row[field_name] = cells[position]

        email = normalize_optional(row.get("email"))
        if not email:
            errors.append(f"第 {idx} 行缺少邮箱地址")
            continue

        row["email"] = email.lower()
        rows.append(row)

    return rows, errors


def compute_overview(accounts: Iterable[Account]) -> OverviewResponse:
    account_list = list(accounts)
    latest_check = max((account.last_check_at for account in account_list if account.last_check_at), default=None)

    return OverviewResponse(
        total_accounts=len(account_list),
        healthy_accounts=sum(1 for account in account_list if account.status == "ready"),
        attention_accounts=sum(1 for account in account_list if account.status != "ready"),
        tokenless_accounts=sum(1 for account in account_list if not account.access_token and not account.refresh_token),
        groups=sorted({normalize_group_name(account.group_name) for account in account_list}),
        latest_check_at=latest_check,
    )


def update_status_from_check(account: Account, result: Dict[str, Any]) -> CheckResult:
    account.last_check_at = datetime.utcnow()

    if result.get("display_name"):
        account.display_name = result["display_name"]

    if result.get("success") and result.get("mail_access"):
        account.status = "ready"
        account.status_message = result.get("message") or "收件箱访问正常"
    elif result.get("success"):
        account.status = "insufficient_scope"
        account.status_message = result.get("message") or "鉴权成功，但缺少读取邮件权限"
    else:
        account.status = "failed"
        account.status_message = result.get("error") or "连接检测失败"

    return CheckResult(
        id=account.id,
        email=account.email,
        success=bool(result.get("success")),
        status=account.status,
        message=account.status_message or "",
        mail_access=bool(result.get("mail_access")),
    )


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview", response_model=OverviewResponse)
async def overview(db: Session = Depends(get_db)) -> OverviewResponse:
    accounts = db.query(Account).order_by(Account.updated_at.desc()).all()
    return compute_overview(accounts)


@app.get("/api/accounts", response_model=list[AccountListItem])
async def list_accounts(db: Session = Depends(get_db)) -> list[AccountListItem]:
    accounts = db.query(Account).order_by(Account.updated_at.desc(), Account.id.desc()).all()
    return [account_to_list_item(account) for account in accounts]


@app.get("/api/accounts/{account_id}", response_model=AccountDetail)
async def get_account(account_id: int, db: Session = Depends(get_db)) -> AccountDetail:
    return account_to_detail(get_account_or_404(db, account_id))


@app.post("/api/accounts", response_model=AccountDetail)
async def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> AccountDetail:
    if db.query(Account).filter(Account.email == payload.email).first():
        raise HTTPException(status_code=409, detail="该邮箱已存在")

    account = Account(email=payload.email)
    apply_account_values(account, payload.model_dump(), allow_blank_clear=True)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account_to_detail(account)


@app.patch("/api/accounts/{account_id}", response_model=AccountDetail)
async def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)) -> AccountDetail:
    account = get_account_or_404(db, account_id)
    values = payload.model_dump(exclude_unset=True)

    new_email = values.get("email")
    if new_email and new_email != account.email:
        duplicate = db.query(Account).filter(Account.email == new_email, Account.id != account_id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="新的邮箱地址与现有账号冲突")

    apply_account_values(account, values, allow_blank_clear=True)
    db.commit()
    db.refresh(account)
    return account_to_detail(account)


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    account = get_account_or_404(db, account_id)
    db.delete(account)
    db.commit()
    return {"success": True}


@app.post("/api/accounts/batch-delete")
async def batch_delete(payload: BatchIdsRequest, db: Session = Depends(get_db)) -> dict[str, int]:
    if not payload.ids:
        raise HTTPException(status_code=400, detail="请至少选择一个账号")

    deleted = db.query(Account).filter(Account.id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


@app.post("/api/accounts/import-text")
async def import_text(payload: ImportTextRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows, errors = parse_import_rows(payload.text)
    if not rows and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    created = 0
    updated = 0
    for row in rows:
        account = db.query(Account).filter(Account.email == row["email"]).first()
        if account is None:
            account = Account(email=row["email"])
            db.add(account)
            created += 1
        else:
            updated += 1
        apply_account_values(account, row, allow_blank_clear=False)

    db.commit()
    return {"created": created, "updated": updated, "failed": len(errors), "errors": errors}


@app.post("/api/accounts/{account_id}/tokens", response_model=AccountDetail)
async def update_tokens(account_id: int, payload: TokenPayload, db: Session = Depends(get_db)) -> AccountDetail:
    account = get_account_or_404(db, account_id)
    apply_account_values(
        account,
        {
            "access_token": payload.access_token,
            "refresh_token": payload.refresh_token,
            "client_id": payload.client_id,
            "client_secret": payload.client_secret,
            "tenant_id": payload.tenant_id,
        },
        allow_blank_clear=True,
    )

    if payload.expires_in:
        account.token_expires_at = datetime.utcnow() + timedelta(seconds=payload.expires_in)

    db.commit()
    db.refresh(account)
    return account_to_detail(account)


@app.post("/api/accounts/{account_id}/check", response_model=CheckResult)
async def check_account(account_id: int, db: Session = Depends(get_db)) -> CheckResult:
    account = get_account_or_404(db, account_id)
    seed_status(account)

    if not account.access_token and not account.refresh_token:
        result = {"success": False, "mail_access": False, "error": "请先提供 access_token 或 refresh_token"}
        response = update_status_from_check(account, result)
        db.commit()
        return response

    response = update_status_from_check(account, await OutlookService(account).test_connection())
    db.commit()
    return response


@app.post("/api/accounts/batch-check", response_model=list[CheckResult])
async def batch_check(payload: BatchIdsRequest, db: Session = Depends(get_db)) -> list[CheckResult]:
    if not payload.ids:
        raise HTTPException(status_code=400, detail="请至少选择一个账号")

    accounts = db.query(Account).filter(Account.id.in_(payload.ids)).order_by(Account.id.asc()).all()
    results: list[CheckResult] = []

    for account in accounts:
        seed_status(account)
        if not account.access_token and not account.refresh_token:
            result = {"success": False, "mail_access": False, "error": "请先提供 access_token 或 refresh_token"}
        else:
            result = await OutlookService(account).test_connection()
        results.append(update_status_from_check(account, result))

    db.commit()
    return results


@app.get("/api/accounts/{account_id}/emails", response_model=EmailListResponse)
async def fetch_emails(account_id: int, limit: int = 20, db: Session = Depends(get_db)) -> EmailListResponse:
    account = get_account_or_404(db, account_id)
    if not account.access_token and not account.refresh_token:
        raise HTTPException(status_code=400, detail="该账号未保存可用令牌")

    try:
        messages = await OutlookService(account).fetch_emails(top=limit)
    except GraphApiError as error:
        raise HTTPException(status_code=400, detail=error.message) from error

    account.last_sync_at = datetime.utcnow()
    if account.status != "ready":
        account.status = "ready"
        account.status_message = "最近一次收件箱读取成功"
    db.commit()

    return EmailListResponse(account_id=account.id, email=account.email, messages=messages)


@app.get("/api/accounts/export.csv")
async def export_csv(db: Session = Depends(get_db)) -> StreamingResponse:
    accounts = db.query(Account).order_by(Account.created_at.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "email",
            "display_name",
            "group_name",
            "password",
            "client_id",
            "client_secret",
            "tenant_id",
            "refresh_token",
            "access_token",
            "status",
            "status_message",
            "last_check_at",
            "last_sync_at",
            "note",
        ]
    )

    for account in accounts:
        writer.writerow(
            [
                account.email,
                account.display_name or "",
                account.group_name or "",
                account.password or "",
                account.client_id or "",
                account.client_secret or "",
                account.tenant_id or "",
                account.refresh_token or "",
                account.access_token or "",
                account.status,
                account.status_message or "",
                account.last_check_at.isoformat() if account.last_check_at else "",
                account.last_sync_at.isoformat() if account.last_sync_at else "",
                account.note or "",
            ]
        )

    buffer = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    filename = f"outlook_accounts_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
