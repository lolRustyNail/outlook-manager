from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    display_name = Column(String(255), nullable=True)
    group_name = Column(String(120), nullable=True, default="默认分组")
    password = Column(Text, nullable=True)
    note = Column(Text, nullable=True)

    client_id = Column(String(255), nullable=True)
    client_secret = Column(String(255), nullable=True)
    tenant_id = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    auth_mode = Column(String(40), nullable=False, default="manual_token")

    is_active = Column(Boolean, nullable=False, default=True)
    status = Column(String(60), nullable=False, default="pending")
    status_message = Column(Text, nullable=True)
    last_check_at = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
