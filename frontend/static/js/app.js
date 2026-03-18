const STATUS_LABELS = {
    ready: "正常",
    pending: "待检查",
    insufficient_scope: "权限不足",
    failed: "检查失败",
    needs_token: "缺少令牌",
};

const AUTH_MODE_LABELS = {
    "refresh+access": "双令牌",
    refresh_token: "刷新令牌",
    access_token: "访问令牌",
    password_archive: "仅密码归档",
    manual_token: "手动录入",
};

const MESSAGE_MAP = {
    "Authentication succeeded and inbox access works": "鉴权成功，收件箱访问正常",
    "Authentication succeeded": "鉴权成功",
    "Inbox access works": "收件箱访问正常",
    "Authentication works but mail read scope is missing": "鉴权成功，但缺少读取邮件权限",
    "Connection check failed": "连接检测失败",
    "No access token or refresh token is available yet": "暂未提供 access_token 或 refresh_token",
    "Please provide an access token or refresh token first": "请先提供 access_token 或 refresh_token",
    "Last inbox fetch succeeded": "最近一次收件箱读取成功",
};

const DEFAULT_GROUP_LABEL = "默认分组";

const state = {
    accounts: [],
    overview: null,
    selectedIds: new Set(),
    activeAccountId: null,
    activeAccountDetail: null,
    emails: [],
    activeEmailId: null,
};

const elements = {
    searchInput: document.getElementById("searchInput"),
    statusFilter: document.getElementById("statusFilter"),
    groupFilter: document.getElementById("groupFilter"),
    selectAll: document.getElementById("selectAll"),
    accountsTableBody: document.getElementById("accountsTableBody"),
    emptyState: document.getElementById("emptyState"),
    detailPanel: document.getElementById("detailPanel"),
    accountForm: document.getElementById("accountForm"),
    passwordForm: document.getElementById("passwordForm"),
    importText: document.getElementById("importText"),
    mailList: document.getElementById("mailList"),
    mailPreview: document.getElementById("mailPreview"),
    mailSearchInput: document.getElementById("mailSearchInput"),
    loadingOverlay: document.getElementById("loadingOverlay"),
    loadingText: document.getElementById("loadingText"),
    toastContainer: document.getElementById("toastContainer"),
};

async function api(path, options = {}) {
    const config = { ...options };
    config.headers = { ...(options.headers || {}) };

    if (config.body && !(config.body instanceof FormData) && !config.headers["Content-Type"]) {
        config.headers["Content-Type"] = "application/json";
    }

    const response = await fetch(path, config);
    if (!response.ok) {
        let message = "请求失败";
        try {
            const payload = await response.json();
            message = payload.detail || payload.message || message;
        } catch (error) {
            message = (await response.text()) || message;
        }
        throw new Error(normalizeMessage(message));
    }

    const contentType = response.headers.get("content-type") || "";
    return contentType.includes("application/json") ? response.json() : response;
}

function normalizeMessage(message) {
    if (!message) return "暂无说明";
    return MESSAGE_MAP[message] || message;
}

function statusLabel(status) {
    return STATUS_LABELS[status] || status || "未知状态";
}

function displayGroup(groupName) {
    if (!groupName || groupName === "Default") return DEFAULT_GROUP_LABEL;
    return groupName;
}

function authModeLabel(mode) {
    return AUTH_MODE_LABELS[mode] || mode || "未识别";
}

function showLoading(text = "加载中...") {
    elements.loadingText.textContent = text;
    elements.loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
    elements.loadingOverlay.classList.add("hidden");
}

function toast(message, type = "info") {
    const node = document.createElement("div");
    node.className = `toast toast-${type}`;
    node.textContent = normalizeMessage(message);
    elements.toastContainer.appendChild(node);
    setTimeout(() => {
        node.classList.add("toast-exit");
        setTimeout(() => node.remove(), 220);
    }, 2400);
}

function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
}

function formatDate(value) {
    if (!value) return "未记录";
    return new Date(value).toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
}

function statusClass(status) {
    if (status === "ready") return "status success";
    if (status === "pending") return "status pending";
    if (status === "insufficient_scope") return "status warning";
    if (status === "needs_token") return "status neutral";
    return "status danger";
}

function maskSecret(value) {
    if (!value) return "未填写";
    if (value.length <= 8) return `${value.slice(0, 1)}***`;
    return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

async function copyText(value, label) {
    if (!value) {
        toast(`${label}为空，无法复制`, "error");
        return;
    }

    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(value);
        } else {
            const input = document.createElement("textarea");
            input.value = value;
            input.setAttribute("readonly", "readonly");
            input.style.position = "absolute";
            input.style.left = "-9999px";
            document.body.appendChild(input);
            input.select();
            document.execCommand("copy");
            input.remove();
        }
        toast(`${label}已复制`, "success");
    } catch (error) {
        toast(`复制${label}失败`, "error");
    }
}

function filteredAccounts() {
    const keyword = elements.searchInput.value.trim().toLowerCase();
    const status = elements.statusFilter.value;
    const group = elements.groupFilter.value;

    return state.accounts.filter((account) => {
        const matchesKeyword =
            !keyword
            || account.email.toLowerCase().includes(keyword)
            || (account.display_name || "").toLowerCase().includes(keyword)
            || displayGroup(account.group_name).toLowerCase().includes(keyword)
            || statusLabel(account.status).toLowerCase().includes(keyword);

        const matchesStatus = status === "all" || account.status === status;
        const matchesGroup = group === "all" || displayGroup(account.group_name) === group;
        return matchesKeyword && matchesStatus && matchesGroup;
    });
}

function renderOverview() {
    const overview = state.overview || {
        total_accounts: 0,
        healthy_accounts: 0,
        attention_accounts: 0,
        tokenless_accounts: 0,
        groups: [],
    };

    document.getElementById("statTotal").textContent = overview.total_accounts;
    document.getElementById("statHealthy").textContent = overview.healthy_accounts;
    document.getElementById("statAttention").textContent = overview.attention_accounts;
    document.getElementById("statTokenless").textContent = overview.tokenless_accounts;

    const currentGroup = elements.groupFilter.value;
    const groups = ["all", ...(overview.groups || []).map(displayGroup)];
    elements.groupFilter.innerHTML = groups
        .map((group) => (
            group === "all"
                ? '<option value="all">全部分组</option>'
                : `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`
        ))
        .join("");

    if (groups.includes(currentGroup)) {
        elements.groupFilter.value = currentGroup;
    }
}

function renderAccounts() {
    const accounts = filteredAccounts();
    elements.emptyState.classList.toggle("hidden", accounts.length > 0);

    if (accounts.length === 0) {
        elements.accountsTableBody.innerHTML = "";
        elements.selectAll.checked = false;
        return;
    }

    elements.accountsTableBody.innerHTML = accounts.map((account) => `
        <tr data-account-id="${account.id}" class="${state.activeAccountId === account.id ? "row-active" : ""}">
            <td class="checkbox-cell"><input type="checkbox" data-select-id="${account.id}" ${state.selectedIds.has(account.id) ? "checked" : ""}></td>
            <td>
                <div class="account-cell compact">
                    <strong>${escapeHtml(account.email)}</strong>
                    <div class="inline-copy-row">
                        <small>${escapeHtml(account.display_name || "未填写显示名称")}</small>
                        <button class="mini-copy-btn" type="button" data-copy-field="email" data-copy-value="${escapeHtml(account.email || "")}">复制</button>
                    </div>
                </div>
            </td>
            <td>
                <div class="password-cell">
                    <strong>${escapeHtml(account.password || "未填写")}</strong>
                    <button class="mini-copy-btn" type="button" data-copy-field="password" data-copy-value="${escapeHtml(account.password || "")}">复制</button>
                </div>
            </td>
            <td>${escapeHtml(authModeLabel(account.auth_mode))}</td>
            <td>
                <div class="status-cell">
                    <span class="${statusClass(account.status)}">${escapeHtml(statusLabel(account.status))}</span>
                    <small>${escapeHtml(normalizeMessage(account.status_message) || "暂无说明")}</small>
                </div>
            </td>
            <td>${escapeHtml(formatDate(account.last_check_at))}</td>
            <td>
                <div class="row-actions">
                    <button class="table-btn" type="button" data-action="password" data-id="${account.id}">改密</button>
                    <button class="table-btn" type="button" data-action="check" data-id="${account.id}">检测</button>
                    <button class="table-btn" type="button" data-action="mail" data-id="${account.id}">邮件</button>
                    <button class="table-btn danger" type="button" data-action="delete" data-id="${account.id}">删除</button>
                </div>
            </td>
        </tr>
    `).join("");

    elements.selectAll.checked = accounts.length > 0 && accounts.every((item) => state.selectedIds.has(item.id));
}

function renderDetailPanel() {
    const account = state.activeAccountDetail;
    if (!account) {
        elements.detailPanel.innerHTML = `
            <div class="detail-placeholder">
                <h3>账号详情</h3>
                <p>选中一条账号后，这里显示精简信息和常用操作。</p>
            </div>
        `;
        return;
    }

    const message = normalizeMessage(account.status_message);
    const credentialPills = [
        account.has_password ? '<span class="mini-pill">密码归档</span>' : "",
        account.has_access_token ? '<span class="mini-pill success">访问令牌</span>' : "",
        account.has_refresh_token ? '<span class="mini-pill info">刷新令牌</span>' : "",
    ].filter(Boolean).join("");

    elements.detailPanel.innerHTML = `
        <div class="detail-header">
            <div>
                <span class="detail-kicker">${escapeHtml(displayGroup(account.group_name))}</span>
                <h3>${escapeHtml(account.email)}</h3>
                <p>${escapeHtml(account.display_name || "未填写显示名称")}</p>
            </div>
            <div class="detail-actions">
                <button class="btn btn-muted" type="button" data-action="edit" data-id="${account.id}">编辑</button>
                <button class="btn btn-primary" type="button" data-action="detail-check" data-id="${account.id}">立即检测</button>
            </div>
        </div>

        <div class="detail-summary">
            <div class="summary-item">
                <span>当前状态</span>
                <strong>${escapeHtml(statusLabel(account.status))}</strong>
            </div>
            <div class="summary-item">
                <span>接入方式</span>
                <strong>${escapeHtml(authModeLabel(account.auth_mode))}</strong>
            </div>
            <div class="summary-item">
                <span>最近检测</span>
                <strong>${escapeHtml(formatDate(account.last_check_at))}</strong>
            </div>
            <div class="summary-item">
                <span>最近收信</span>
                <strong>${escapeHtml(formatDate(account.last_sync_at))}</strong>
            </div>
        </div>

        <div class="detail-section">
            <h4>当前说明</h4>
            <p>${escapeHtml(message || "暂无说明")}</p>
        </div>

        <div class="detail-section">
            <h4>账号与密码</h4>
            <div class="credential-grid">
                <div class="credential-item">
                    <span>账号</span>
                    <strong>${escapeHtml(account.email || "未填写")}</strong>
                    <button class="copy-btn" type="button" data-copy-field="email">复制账号</button>
                </div>
                <div class="credential-item">
                    <span>密码</span>
                    <strong>${escapeHtml(account.password || "未填写")}</strong>
                    <button class="copy-btn" type="button" data-copy-field="password">复制密码</button>
                </div>
            </div>
        </div>

        <div class="detail-section">
            <h4>凭据情况</h4>
            <div class="mini-pill-row">${credentialPills || '<span class="mini-pill muted">暂无凭据</span>'}</div>
            <div class="token-grid">
                <div class="token-item">
                    <span>访问令牌</span>
                    <strong>${escapeHtml(maskSecret(account.access_token))}</strong>
                    <small>${account.token_expires_at ? `过期时间：${formatDate(account.token_expires_at)}` : "未记录过期时间"}</small>
                </div>
                <div class="token-item">
                    <span>刷新令牌</span>
                    <strong>${escapeHtml(maskSecret(account.refresh_token))}</strong>
                    <small>客户端 ID：${escapeHtml(account.client_id || "使用默认公共客户端")}</small>
                </div>
            </div>
        </div>

        <div class="detail-section">
            <h4>备注</h4>
            <p>${escapeHtml(account.note || "暂无备注")}</p>
        </div>

        <div class="detail-footer">
            <button class="btn btn-muted" type="button" data-action="detail-password" data-id="${account.id}">修改密码</button>
            <button class="btn btn-secondary" type="button" data-action="detail-mail" data-id="${account.id}">查看邮件</button>
            <button class="btn btn-danger" type="button" data-action="detail-delete" data-id="${account.id}">删除账号</button>
        </div>
    `;
}

async function loadOverview() {
    state.overview = await api("/api/overview");
    renderOverview();
}

async function loadAccounts() {
    state.accounts = await api("/api/accounts");

    if (state.activeAccountId) {
        const summary = state.accounts.find((item) => item.id === state.activeAccountId);
        if (!summary) {
            state.activeAccountId = null;
            state.activeAccountDetail = null;
        } else if (state.activeAccountDetail) {
            state.activeAccountDetail = { ...state.activeAccountDetail, ...summary };
        }
    }

    renderAccounts();
    renderDetailPanel();

    if (!state.activeAccountId && state.accounts.length > 0) {
        await selectAccount(state.accounts[0].id);
    }
}

async function refreshPage() {
    await loadOverview();
    await loadAccounts();
}

async function selectAccount(accountId) {
    state.activeAccountId = accountId;
    renderAccounts();
    elements.detailPanel.innerHTML = `
        <div class="detail-placeholder">
            <h3>账号详情</h3>
            <p>正在加载账号信息...</p>
        </div>
    `;
    state.activeAccountDetail = await api(`/api/accounts/${accountId}`);
    renderDetailPanel();
}

function fillAccountForm(account = null) {
    document.getElementById("accountId").value = account ? account.id : "";
    document.getElementById("email").value = account ? account.email || "" : "";
    document.getElementById("display_name").value = account ? account.display_name || "" : "";
    document.getElementById("group_name").value = account ? displayGroup(account.group_name) : DEFAULT_GROUP_LABEL;
    document.getElementById("password").value = account ? account.password || "" : "";
    document.getElementById("note").value = account ? account.note || "" : "";
    document.getElementById("client_id").value = account ? account.client_id || "" : "";
    document.getElementById("client_secret").value = account ? account.client_secret || "" : "";
    document.getElementById("tenant_id").value = account ? account.tenant_id || "" : "";
    document.getElementById("refresh_token").value = account ? account.refresh_token || "" : "";
    document.getElementById("access_token").value = account ? account.access_token || "" : "";
    document.getElementById("is_active").value = account && !account.is_active ? "false" : "true";
    document.getElementById("accountModalTitle").textContent = account ? "编辑账号" : "新增账号";
}

function openPasswordModal(accountId) {
    const account = state.accounts.find((item) => item.id === accountId) || state.activeAccountDetail;
    if (!account) {
        toast("未找到账号信息", "error");
        return;
    }

    document.getElementById("passwordAccountId").value = account.id;
    document.getElementById("passwordAccountEmail").value = account.email || "";
    document.getElementById("passwordValue").value = account.password || "";
    openModal("passwordModal");
    document.getElementById("passwordValue").focus();
    document.getElementById("passwordValue").select();
}

function gatherAccountForm() {
    return {
        email: document.getElementById("email").value,
        display_name: document.getElementById("display_name").value,
        group_name: document.getElementById("group_name").value,
        password: document.getElementById("password").value,
        note: document.getElementById("note").value,
        client_id: document.getElementById("client_id").value,
        client_secret: document.getElementById("client_secret").value,
        tenant_id: document.getElementById("tenant_id").value,
        refresh_token: document.getElementById("refresh_token").value,
        access_token: document.getElementById("access_token").value,
        is_active: document.getElementById("is_active").value === "true",
    };
}

async function saveAccount(event) {
    event.preventDefault();
    const accountId = document.getElementById("accountId").value;
    const payload = gatherAccountForm();
    showLoading(accountId ? "正在保存账号..." : "正在创建账号...");

    try {
        await api(accountId ? `/api/accounts/${accountId}` : "/api/accounts", {
            method: accountId ? "PATCH" : "POST",
            body: JSON.stringify(payload),
        });
        toast(accountId ? "账号已更新" : "账号已创建", "success");
        closeModal("accountModal");
        await refreshPage();
        if (state.activeAccountId) {
            await selectAccount(Number(state.activeAccountId));
        }
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

async function savePassword(event) {
    event.preventDefault();
    const accountId = document.getElementById("passwordAccountId").value;
    const password = document.getElementById("passwordValue").value;

    if (!accountId) {
        toast("未找到账号", "error");
        return;
    }

    showLoading("正在保存密码...");
    try {
        await api(`/api/accounts/${accountId}`, {
            method: "PATCH",
            body: JSON.stringify({ password }),
        });
        closeModal("passwordModal");
        toast("密码已更新", "success");
        await refreshPage();
        if (state.activeAccountId === Number(accountId)) {
            await selectAccount(Number(accountId));
        }
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

async function editAccount(accountId) {
    showLoading("正在读取账号...");
    try {
        fillAccountForm(await api(`/api/accounts/${accountId}`));
        openModal("accountModal");
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

async function removeAccount(accountId) {
    const target = state.accounts.find((item) => item.id === accountId);
    if (!window.confirm(`确定删除账号 ${target?.email || ""} 吗？`)) return;

    showLoading("正在删除账号...");
    try {
        await api(`/api/accounts/${accountId}`, { method: "DELETE" });
        state.selectedIds.delete(accountId);
        if (state.activeAccountId === accountId) {
            state.activeAccountId = null;
            state.activeAccountDetail = null;
        }
        toast("账号已删除", "success");
        await refreshPage();
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

async function batchDelete() {
    if (state.selectedIds.size === 0) {
        toast("请先选择账号", "error");
        return;
    }

    if (!window.confirm(`确定删除选中的 ${state.selectedIds.size} 个账号吗？`)) return;

    showLoading("正在批量删除...");
    try {
        const result = await api("/api/accounts/batch-delete", {
            method: "POST",
            body: JSON.stringify({ ids: Array.from(state.selectedIds) }),
        });
        state.selectedIds.clear();
        toast(`已删除 ${result.deleted} 个账号`, "success");
        await refreshPage();
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

async function runCheck(accountId) {
    showLoading("正在检测账号...");
    try {
        const result = await api(`/api/accounts/${accountId}/check`, { method: "POST" });
        toast(result.message, result.success ? "success" : "error");
        await refreshPage();
        if (state.activeAccountId === accountId) {
            await selectAccount(accountId);
        }
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

async function batchCheck() {
    if (state.selectedIds.size === 0) {
        toast("请先选择账号", "error");
        return;
    }

    showLoading(`正在检测 ${state.selectedIds.size} 个账号...`);
    try {
        const results = await api("/api/accounts/batch-check", {
            method: "POST",
            body: JSON.stringify({ ids: Array.from(state.selectedIds) }),
        });
        const readyCount = results.filter((item) => item.status === "ready").length;
        const warningCount = results.filter((item) => item.status === "insufficient_scope").length;
        const failCount = results.filter((item) => item.status === "failed" || item.status === "needs_token").length;
        toast(`检测完成：正常 ${readyCount} 个，警告 ${warningCount} 个，失败 ${failCount} 个`, "info");
        await refreshPage();
        if (state.activeAccountId) {
            await selectAccount(state.activeAccountId);
        }
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

async function exportCsv() {
    showLoading("正在导出 CSV...");
    try {
        const response = await fetch("/api/accounts/export.csv");
        if (!response.ok) throw new Error("导出失败");

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `outlook_accounts_${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(url);
        toast("CSV 导出成功", "success");
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

async function submitImport() {
    const text = elements.importText.value.trim();
    if (!text) {
        toast("请先粘贴导入数据", "error");
        return;
    }

    showLoading("正在导入账号...");
    try {
        const result = await api("/api/accounts/import-text", {
            method: "POST",
            body: JSON.stringify({ text }),
        });
        toast(
            `导入完成：新增 ${result.created} 个，更新 ${result.updated} 个，失败 ${result.failed} 个`,
            result.failed ? "info" : "success",
        );
        elements.importText.value = "";
        closeModal("importModal");
        await refreshPage();
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

function filteredEmails() {
    const keyword = elements.mailSearchInput.value.trim().toLowerCase();
    if (!keyword) return state.emails;

    return state.emails.filter((mail) =>
        (mail.subject || "").toLowerCase().includes(keyword)
        || (mail.from_name || "").toLowerCase().includes(keyword)
        || (mail.from_address || "").toLowerCase().includes(keyword)
    );
}

function renderMailList() {
    const mails = filteredEmails();
    if (mails.length === 0) {
        elements.mailList.innerHTML = `
            <div class="detail-placeholder">
                <h3>没有邮件</h3>
                <p>当前没有匹配的邮件。</p>
            </div>
        `;
        return;
    }

    elements.mailList.innerHTML = mails.map((mail) => `
        <button class="${state.activeEmailId === mail.id ? "mail-item active" : "mail-item"}" type="button" data-mail-id="${mail.id}">
            <strong>${escapeHtml(mail.subject || "（无主题）")}</strong>
            <span>${escapeHtml(mail.from_name || mail.from_address || "未知发件人")}</span>
            <small>${escapeHtml(formatDate(mail.received_date))}</small>
            <p>${escapeHtml(mail.preview || "")}</p>
        </button>
    `).join("");
}

function renderMailPreview() {
    const mail = state.emails.find((item) => item.id === state.activeEmailId);
    if (!mail) {
        elements.mailPreview.innerHTML = `
            <div class="detail-placeholder">
                <h3>邮件预览</h3>
                <p>从左侧选择一封邮件后，在这里查看正文。</p>
            </div>
        `;
        return;
    }

    elements.mailPreview.innerHTML = `
        <div class="mail-preview-header">
            <h3>${escapeHtml(mail.subject || "（无主题）")}</h3>
            <p>发件人：${escapeHtml(mail.from_name || mail.from_address || "未知")}</p>
            <p>时间：${escapeHtml(formatDate(mail.received_date))}</p>
        </div>
        <iframe class="mail-frame" id="mailFrame"></iframe>
    `;

    document.getElementById("mailFrame").srcdoc = mail.body_html || `<pre>${escapeHtml(mail.preview || "")}</pre>`;
}

async function openMailModal(accountId) {
    const account = state.accounts.find((item) => item.id === accountId);
    document.getElementById("emailModalTitle").textContent = `邮件预览 - ${account?.email || ""}`;
    state.emails = [];
    state.activeEmailId = null;
    renderMailList();
    renderMailPreview();
    openModal("emailModal");

    showLoading("正在读取收件箱...");
    try {
        const payload = await api(`/api/accounts/${accountId}/emails?limit=20`);
        state.emails = payload.messages || [];
        state.activeEmailId = state.emails[0]?.id || null;
        renderMailList();
        renderMailPreview();
        await refreshPage();
        if (state.activeAccountId === accountId) {
            await selectAccount(accountId);
        }
    } catch (error) {
        toast(error.message, "error");
        closeModal("emailModal");
    } finally {
        hideLoading();
    }
}

function handleTableClick(event) {
    const copyButton = event.target.closest("[data-copy-field][data-copy-value]");
    if (copyButton) {
        const label = copyButton.dataset.copyField === "password" ? "密码" : "账号";
        copyText(copyButton.dataset.copyValue || "", label);
        return;
    }

    const actionButton = event.target.closest("[data-action]");
    if (actionButton) {
        const accountId = Number(actionButton.dataset.id);
        const action = actionButton.dataset.action;
        if (action === "password") openPasswordModal(accountId);
        if (action === "check") runCheck(accountId);
        if (action === "mail") openMailModal(accountId);
        if (action === "delete") removeAccount(accountId);
        return;
    }

    if (!event.target.closest("[data-select-id]")) {
        const row = event.target.closest("tr[data-account-id]");
        if (row) selectAccount(Number(row.dataset.accountId));
    }
}

function handleTableChange(event) {
    const checkbox = event.target.closest("[data-select-id]");
    if (!checkbox) return;

    const accountId = Number(checkbox.dataset.selectId);
    if (checkbox.checked) {
        state.selectedIds.add(accountId);
    } else {
        state.selectedIds.delete(accountId);
        elements.selectAll.checked = false;
    }
}

function handleDetailClick(event) {
    const copyField = event.target.dataset.copyField;
    if (copyField && state.activeAccountDetail) {
        if (copyField === "email") copyText(state.activeAccountDetail.email || "", "账号");
        if (copyField === "password") copyText(state.activeAccountDetail.password || "", "密码");
        return;
    }

    const action = event.target.dataset.action;
    const accountId = Number(event.target.dataset.id);
    if (!action || !accountId) return;

    if (action === "edit") editAccount(accountId);
    if (action === "detail-password") openPasswordModal(accountId);
    if (action === "detail-check") runCheck(accountId);
    if (action === "detail-mail") openMailModal(accountId);
    if (action === "detail-delete") removeAccount(accountId);
}

function bindEvents() {
    document.getElementById("refreshBtn").addEventListener("click", refreshPage);
    document.getElementById("addBtn").addEventListener("click", () => {
        fillAccountForm();
        openModal("accountModal");
    });
    document.getElementById("importBtn").addEventListener("click", () => openModal("importModal"));
    document.getElementById("navAdd").addEventListener("click", () => {
        fillAccountForm();
        openModal("accountModal");
    });
    document.getElementById("navImport").addEventListener("click", () => openModal("importModal"));
    document.getElementById("navExport").addEventListener("click", exportCsv);
    document.getElementById("batchDeleteBtn").addEventListener("click", batchDelete);
    document.getElementById("batchCheckBtn").addEventListener("click", batchCheck);
    document.getElementById("exportBtn").addEventListener("click", exportCsv);
    document.getElementById("submitImportBtn").addEventListener("click", submitImport);

    elements.accountForm.addEventListener("submit", saveAccount);
    elements.passwordForm.addEventListener("submit", savePassword);
    elements.searchInput.addEventListener("input", renderAccounts);
    elements.statusFilter.addEventListener("change", renderAccounts);
    elements.groupFilter.addEventListener("change", renderAccounts);
    elements.accountsTableBody.addEventListener("click", handleTableClick);
    elements.accountsTableBody.addEventListener("change", handleTableChange);
    elements.detailPanel.addEventListener("click", handleDetailClick);

    elements.mailSearchInput.addEventListener("input", () => {
        renderMailList();
        if (!filteredEmails().find((mail) => mail.id === state.activeEmailId)) {
            state.activeEmailId = filteredEmails()[0]?.id || null;
        }
        renderMailPreview();
    });

    elements.selectAll.addEventListener("change", (event) => {
        filteredAccounts().forEach((account) => {
            if (event.target.checked) state.selectedIds.add(account.id);
            else state.selectedIds.delete(account.id);
        });
        renderAccounts();
    });

    document.querySelectorAll("[data-close]").forEach((button) => {
        button.addEventListener("click", () => closeModal(button.dataset.close));
    });

    document.querySelectorAll(".modal").forEach((modal) => {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) modal.classList.add("hidden");
        });
    });

    elements.mailList.addEventListener("click", (event) => {
        const target = event.target.closest("[data-mail-id]");
        if (!target) return;
        state.activeEmailId = target.dataset.mailId;
        renderMailList();
        renderMailPreview();
    });
}

async function bootstrap() {
    bindEvents();
    showLoading("正在加载账号数据...");
    try {
        await refreshPage();
    } catch (error) {
        toast(error.message, "error");
    } finally {
        hideLoading();
    }
}

document.addEventListener("DOMContentLoaded", bootstrap);
