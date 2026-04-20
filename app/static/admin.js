const createUserFormEl = document.getElementById("create-user-form");
const userListEl = document.getElementById("user-list");
const adminStatusEl = document.getElementById("admin-status");
const refreshUsersEl = document.getElementById("refresh-users");
const adminLogoutButtonEl = document.getElementById("admin-logout-button");
const userCardTemplate = document.getElementById("user-card-template");

function setAdminStatus(message, isError = false) {
  adminStatusEl.textContent = message;
  adminStatusEl.classList.toggle("error", isError);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("登录已失效，请重新登录。");
  }
  if (response.status === 403) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : "没有管理员权限。");
  }
  if (!response.ok) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : "请求失败，请稍后重试。");
  }
  return payload;
}

async function logout() {
  try {
    await requestJson("/api/v1/auth/logout", { method: "POST" });
  } catch {
    // ignore
  }
  window.location.href = "/login";
}

function buildUserCard(user) {
  const fragment = userCardTemplate.content.cloneNode(true);
  const nameEl = fragment.querySelector(".user-card-name");
  const metaEl = fragment.querySelector(".user-card-meta");
  const roleBadgeEl = fragment.querySelector(".user-card-role");
  const roleSelectEl = fragment.querySelector(".role-select");
  const activeToggleEl = fragment.querySelector(".active-toggle");
  const updateButtonEl = fragment.querySelector(".update-user");
  const resetFormEl = fragment.querySelector(".reset-password-form");
  const resetInputEl = fragment.querySelector(".reset-password-input");

  nameEl.textContent = user.display_name;
  metaEl.textContent = `${user.username} · 创建于 ${new Date(user.created_at).toLocaleString("zh-CN")}`;
  roleBadgeEl.textContent = user.role === "admin" ? "管理员" : "普通员工";
  roleSelectEl.value = user.role;
  activeToggleEl.checked = user.is_active;

  updateButtonEl.addEventListener("click", async () => {
    try {
      const updated = await requestJson(`/api/v1/admin/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          role: roleSelectEl.value,
          is_active: activeToggleEl.checked,
        }),
      });
      setAdminStatus(`已更新 ${updated.display_name} 的权限。`);
      await loadUsers();
    } catch (error) {
      setAdminStatus(error.message, true);
    }
  });

  resetFormEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await requestJson(`/api/v1/admin/users/${user.id}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ password: resetInputEl.value }),
      });
      resetInputEl.value = "";
      setAdminStatus(`已重置 ${user.display_name} 的密码。`);
    } catch (error) {
      setAdminStatus(error.message, true);
    }
  });

  return fragment;
}

async function loadUsers() {
  const users = await requestJson("/api/v1/admin/users", { method: "GET", headers: {} });
  userListEl.innerHTML = "";
  for (const user of users) {
    userListEl.appendChild(buildUserCard(user));
  }
}

createUserFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const user = await requestJson("/api/v1/admin/users", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("create-username").value.trim(),
        display_name: document.getElementById("create-display-name").value.trim(),
        password: document.getElementById("create-password").value,
        role: document.getElementById("create-role").value,
        is_active: document.getElementById("create-active").checked,
      }),
    });
    createUserFormEl.reset();
    document.getElementById("create-active").checked = true;
    setAdminStatus(`已创建用户 ${user.display_name}。`);
    await loadUsers();
  } catch (error) {
    setAdminStatus(error.message, true);
  }
});

refreshUsersEl.addEventListener("click", () => {
  loadUsers().catch((error) => setAdminStatus(error.message, true));
});

adminLogoutButtonEl.addEventListener("click", logout);

loadUsers().catch((error) => setAdminStatus(error.message, true));
