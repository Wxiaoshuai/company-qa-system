const loginFormEl = document.getElementById("login-form");
const loginStatusEl = document.getElementById("login-status");
const loginButtonEl = document.getElementById("login-button");

function setLoginStatus(message, isError = false) {
  loginStatusEl.textContent = message;
  loginStatusEl.classList.toggle("error", isError);
}

async function requestCurrentUser() {
  const response = await fetch("/api/v1/auth/me", { credentials: "same-origin" });
  if (response.ok) {
    window.location.href = "/";
  }
}

loginFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginButtonEl.disabled = true;
  setLoginStatus("正在登录...");

  const payload = {
    username: document.getElementById("username").value.trim(),
    password: document.getElementById("password").value,
  };

  try {
    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "登录失败，请稍后重试。");
    }
    setLoginStatus("登录成功，正在跳转...");
    window.location.href = "/";
  } catch (error) {
    setLoginStatus(error.message, true);
  } finally {
    loginButtonEl.disabled = false;
  }
});

requestCurrentUser();
