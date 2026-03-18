from __future__ import annotations

import html
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from models import Account


class GraphApiError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class OutlookService:
    DEFAULT_CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
    OUTLOOK_BASE_URL = "https://outlook.office.com/api/v2.0"

    def __init__(self, account: Account):
        self.account = account

    def _token_url(self) -> str:
        tenant = (self.account.tenant_id or "common").strip() or "common"
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    def _client_id(self) -> str:
        return self.account.client_id or self.DEFAULT_CLIENT_ID

    def _token_is_fresh(self) -> bool:
        if not self.account.access_token or self.account.token_expires_at is None:
            return False
        return self.account.token_expires_at > datetime.utcnow() + timedelta(minutes=5)

    async def refresh_access_token(self) -> str:
        if not self.account.refresh_token:
            raise GraphApiError(401, "未提供 refresh_token")

        payload = {
            "client_id": self._client_id(),
            "grant_type": "refresh_token",
            "refresh_token": self.account.refresh_token,
        }
        if self.account.client_secret:
            payload["client_secret"] = self.account.client_secret

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self._token_url(), data=payload) as response:
                data = await self._read_json(response)
                if response.status >= 400:
                    raise GraphApiError(response.status, self._extract_error(data, None))

        access_token = data.get("access_token") if data else None
        if not access_token:
            raise GraphApiError(500, "刷新令牌成功，但返回结果里缺少 access_token")

        self.account.access_token = access_token
        if data.get("refresh_token"):
            self.account.refresh_token = data["refresh_token"]

        expires_in = int(data.get("expires_in", 3600))
        self.account.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        return access_token

    async def ensure_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._token_is_fresh():
            return self.account.access_token or ""

        if self.account.refresh_token:
            return await self.refresh_access_token()

        if self.account.access_token and not force_refresh:
            return self.account.access_token

        raise GraphApiError(401, "未提供 access_token 或 refresh_token")

    async def outlook_get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        token = await self.ensure_access_token()
        response = await self._request_json(token, path, params)

        if response["status"] == 401 and self.account.refresh_token:
            token = await self.ensure_access_token(force_refresh=True)
            response = await self._request_json(token, path, params)

        if response["status"] >= 400:
            raise GraphApiError(response["status"], self._extract_error(response["data"], response["text"]))

        return response["data"] or {}

    async def _request_json(self, token: str, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            "Authorization": f"Bearer {token}",
            "Cache-Control": "no-cache",
            "Prefer": "odata.maxpagesize=50",
        }
        url = f"{self.OUTLOOK_BASE_URL}{path}"
        params = params or {}
        params["_t"] = str(int(datetime.utcnow().timestamp() * 1000))

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await self._read_json(response)
                text = None
                if data is None:
                    text = await response.text()
                return {"status": response.status, "data": data, "text": text}

    async def _read_json(self, response: aiohttp.ClientResponse) -> Optional[Dict[str, Any]]:
        try:
            return await response.json(content_type=None)
        except Exception:
            return None

    def _extract_error(self, data: Optional[Dict[str, Any]], fallback_text: Optional[str]) -> str:
        if isinstance(data, dict):
            if "error_description" in data:
                message = str(data["error_description"])
            elif isinstance(data.get("error"), dict):
                message = str(data["error"].get("message") or data["error"].get("code") or "Outlook 接口错误")
            elif isinstance(data.get("error"), str):
                message = str(data["error"])
            else:
                message = "Outlook 接口错误"
        else:
            message = fallback_text or "Outlook 接口请求失败"

        lowered = message.lower()
        if "invalid_grant" in lowered:
            return "refresh_token 无效或已过期"
        if "interaction_required" in lowered:
            return "该账号需要重新授权"
        if "access is denied" in lowered or "forbidden" in lowered:
            return "当前令牌缺少足够的邮件权限"
        return message[:240]

    async def test_connection(self) -> Dict[str, Any]:
        try:
            profile = await self.outlook_get("/me")
        except GraphApiError as error:
            return {"success": False, "mail_access": False, "error": error.message}

        result = {
            "success": True,
            "mail_access": False,
            "display_name": profile.get("DisplayName"),
            "user_principal_name": profile.get("EmailAddress"),
            "message": "鉴权成功",
        }

        try:
            await self.outlook_get("/me/mailfolders/inbox/messages", {"$top": "1"})
            result["mail_access"] = True
            result["message"] = "鉴权成功，收件箱访问正常"
        except GraphApiError as error:
            result["mail_access"] = False
            result["message"] = error.message

        return result

    async def fetch_emails(self, top: int = 20, folder: str = "inbox") -> List[Dict[str, Any]]:
        top = max(1, min(top, 50))
        payload = await self.outlook_get(
            f"/me/mailfolders/{folder}/messages",
            {"$top": str(top), "$orderby": "ReceivedDateTime desc"},
        )

        result: List[Dict[str, Any]] = []
        for item in payload.get("value", []):
            from_info = item.get("From", {}).get("EmailAddress", {})
            body = item.get("Body", {}) or {}
            content = body.get("Content") or ""
            content_type = (body.get("ContentType") or "").lower()

            if content_type == "html":
                body_html = content
            else:
                safe_text = html.escape(content or item.get("BodyPreview") or "")
                body_html = f"<pre style='white-space:pre-wrap;font-family:Segoe UI, sans-serif'>{safe_text}</pre>"

            result.append(
                {
                    "id": item.get("Id"),
                    "subject": item.get("Subject") or "（无主题）",
                    "from_name": from_info.get("Name"),
                    "from_address": from_info.get("Address"),
                    "received_date": item.get("DateTimeReceived") or item.get("ReceivedDateTime"),
                    "is_read": bool(item.get("IsRead")),
                    "preview": item.get("BodyPreview"),
                    "body_html": body_html,
                }
            )

        return result
