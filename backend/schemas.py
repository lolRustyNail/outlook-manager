from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AccountBase(BaseModel):
    email: str
    display_name: Optional[str] = None
    group_name: Optional[str] = "默认分组"
    password: Optional[str] = None
    note: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("邮箱格式不正确")
        return cleaned

    @field_validator(
        "group_name",
        "display_name",
        "note",
        "password",
        "client_id",
        "client_secret",
        "tenant_id",
        "access_token",
        "refresh_token",
    )
    @classmethod
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    group_name: Optional[str] = None
    password: Optional[str] = None
    note: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("邮箱格式不正确")
        return cleaned

    @field_validator(
        "display_name",
        "group_name",
        "note",
        "password",
        "client_id",
        "client_secret",
        "tenant_id",
        "access_token",
        "refresh_token",
    )
    @classmethod
    def strip_update_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip()


class AccountListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: Optional[str] = None
    group_name: Optional[str] = None
    auth_mode: str
    is_active: bool
    status: str
    status_message: Optional[str] = None
    has_password: bool
    has_access_token: bool
    has_refresh_token: bool
    token_expires_at: Optional[datetime] = None
    last_check_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class AccountDetail(AccountListItem):
    password: Optional[str] = None
    note: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None


class ImportTextRequest(BaseModel):
    text: str


class BatchIdsRequest(BaseModel):
    ids: list[int]


class TokenPayload(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = 3600
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None


class OverviewResponse(BaseModel):
    total_accounts: int
    healthy_accounts: int
    attention_accounts: int
    tokenless_accounts: int
    groups: list[str]
    latest_check_at: Optional[datetime] = None


class CheckResult(BaseModel):
    id: int
    email: str
    success: bool
    status: str
    message: str
    mail_access: bool = False


class EmailMessage(BaseModel):
    id: str
    subject: Optional[str] = None
    from_name: Optional[str] = None
    from_address: Optional[str] = None
    received_date: Optional[datetime] = None
    is_read: bool = False
    preview: Optional[str] = None
    body_html: Optional[str] = None


class EmailListResponse(BaseModel):
    account_id: int
    email: str
    messages: list[EmailMessage]
