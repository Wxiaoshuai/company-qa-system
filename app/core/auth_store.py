import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@dataclass
class UserRecord:
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    failed_login_attempts: int
    locked_until: str | None
    created_at: str
    updated_at: str
    last_login_at: str | None


class AuthError(RuntimeError):
    pass


class AuthStore:
    def __init__(self) -> None:
        self._initialized_path: str | None = None

    def _db_path(self) -> str:
        return str(settings.auth_db_file)

    @contextmanager
    def connection(self):
        db_path = settings.auth_db_file
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        current_path = self._db_path()
        if self._initialized_path == current_path and settings.auth_db_file.exists():
            return

        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    target_user_id INTEGER,
                    detail TEXT,
                    ip_address TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
        self._initialized_path = current_path

    @staticmethod
    def _hash_password(password: str, salt: str | None = None) -> str:
        salt_value = salt or secrets.token_hex(16)
        iterations = 200_000
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt_value.encode("utf-8"),
            iterations,
        ).hex()
        return f"{salt_value}${iterations}${digest}"

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            salt, iterations, digest = password_hash.split("$", 2)
        except ValueError:
            return False

        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(computed, digest)

    def _row_to_user(self, row: sqlite3.Row | None) -> UserRecord | None:
        if row is None:
            return None
        return UserRecord(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            failed_login_attempts=row["failed_login_attempts"],
            locked_until=row["locked_until"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_login_at=row["last_login_at"],
        )

    def log_event(
        self,
        action: str,
        user_id: int | None = None,
        target_user_id: int | None = None,
        detail: str | None = None,
        ip_address: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        query = """
            INSERT INTO audit_logs (user_id, action, target_user_id, detail, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (user_id, action, target_user_id, detail, ip_address, utc_now_iso())
        if conn is not None:
            conn.execute(query, params)
            return
        with self.connection() as owned_conn:
            owned_conn.execute(query, params)

    def get_user_by_username(self, username: str) -> UserRecord | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username.strip().lower(),),
            ).fetchone()
        return self._row_to_user(row)

    def get_user_by_id(self, user_id: int) -> UserRecord | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row)

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str,
        role: str = "user",
        is_active: bool = True,
    ) -> UserRecord:
        normalized_username = username.strip().lower()
        now = utc_now_iso()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    username, display_name, password_hash, role, is_active,
                    failed_login_attempts, locked_until, created_at, updated_at, last_login_at
                ) VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?, NULL)
                """,
                (
                    normalized_username,
                    display_name.strip(),
                    self._hash_password(password),
                    role,
                    1 if is_active else 0,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM users WHERE username = ?", (normalized_username,)).fetchone()
        return self._row_to_user(row)

    def ensure_admin_user(self) -> None:
        if not settings.auth_init_admin_enabled:
            return
        existing = self.get_user_by_username(settings.auth_init_admin_username)
        if existing is None:
            user = self.create_user(
                username=settings.auth_init_admin_username,
                password=settings.auth_init_admin_password,
                display_name=settings.auth_init_admin_display_name,
                role="admin",
                is_active=True,
            )
            self.log_event("admin_bootstrap", user_id=user.id, target_user_id=user.id, detail="Initial admin created")
            return
        if settings.auth_init_admin_reset_password:
            with self.connection() as conn:
                conn.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (self._hash_password(settings.auth_init_admin_password), datetime.now().isoformat(), existing.id),
                )
            self.log_event("admin_password_reset", user_id=existing.id, target_user_id=existing.id, detail="Admin password reset via config flag")

    def _hash_session_token(self, token: str) -> str:
        return hashlib.sha256(f"{settings.auth_session_secret}:{token}".encode("utf-8")).hexdigest()

    def authenticate(self, username: str, password: str, ip_address: str | None = None) -> UserRecord:
        normalized_username = username.strip().lower()
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (normalized_username,)).fetchone()
            if row is None:
                self.log_event(
                    "login_failed",
                    detail=f"Unknown user: {normalized_username}",
                    ip_address=ip_address,
                    conn=conn,
                )
                raise AuthError("用户名或密码错误。")

            user = self._row_to_user(row)
            if user is None:
                raise AuthError("登录失败，请重试。")

            if not user.is_active:
                self.log_event(
                    "login_blocked",
                    user_id=user.id,
                    detail="Inactive account",
                    ip_address=ip_address,
                    conn=conn,
                )
                raise AuthError("账号已被禁用，请联系管理员。")

            locked_until = parse_datetime(user.locked_until)
            if locked_until is not None and locked_until > utc_now():
                raise AuthError("登录失败次数过多，请稍后再试。")

            if not self.verify_password(password, row["password_hash"]):
                attempts = user.failed_login_attempts + 1
                lock_until = None
                if attempts >= max(1, settings.auth_login_max_attempts):
                    lock_until = (utc_now() + timedelta(minutes=max(1, settings.auth_lock_minutes))).isoformat()
                    attempts = 0
                conn.execute(
                    """
                    UPDATE users
                    SET failed_login_attempts = ?, locked_until = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (attempts, lock_until, utc_now_iso(), user.id),
                )
                self.log_event(
                    "login_failed",
                    user_id=user.id,
                    detail="Invalid password",
                    ip_address=ip_address,
                    conn=conn,
                )
                raise AuthError("用户名或密码错误。")

            now = utc_now_iso()
            conn.execute(
                """
                UPDATE users
                SET failed_login_attempts = 0, locked_until = NULL, last_login_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, user.id),
            )

        fresh = self.get_user_by_username(normalized_username)
        if fresh is None:
            raise AuthError("登录失败，请重试。")
        self.log_event("login_success", user_id=fresh.id, ip_address=ip_address)
        return fresh

    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_session_token(token)
        now = utc_now()
        expires_at = now + timedelta(hours=max(1, settings.auth_session_ttl_hours))
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (user_id, token_hash, created_at, expires_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, token_hash, now.isoformat(), expires_at.isoformat(), now.isoformat()),
            )
        return token

    def get_user_by_session_token(self, token: str | None) -> UserRecord | None:
        if not token:
            return None

        token_hash = self._hash_session_token(token)
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT u.*, s.id AS session_id, s.expires_at
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None

            expires_at = parse_datetime(row["expires_at"])
            if expires_at is None or expires_at <= utc_now():
                conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))
                return None

            if not bool(row["is_active"]):
                conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))
                return None

            conn.execute(
                "UPDATE user_sessions SET last_seen_at = ? WHERE token_hash = ?",
                (utc_now_iso(), token_hash),
            )
        return self.get_user_by_id(row["id"])

    def invalidate_session(self, token: str | None, user_id: int | None = None, ip_address: str | None = None) -> None:
        if not token:
            return
        token_hash = self._hash_session_token(token)
        with self.connection() as conn:
            conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))
        self.log_event("logout", user_id=user_id, ip_address=ip_address)

    def list_users(self) -> list[UserRecord]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
        return [self._row_to_user(row) for row in rows if row is not None]

    def update_user(
        self,
        user_id: int,
        role: str | None = None,
        is_active: bool | None = None,
        display_name: str | None = None,
        password: str | None = None,
    ) -> UserRecord:
        current = self.get_user_by_id(user_id)
        if current is None:
            raise AuthError("用户不存在。")

        updates = {
            "role": role if role is not None else current.role,
            "is_active": 1 if (is_active if is_active is not None else current.is_active) else 0,
            "display_name": display_name.strip() if display_name is not None else current.display_name,
            "updated_at": utc_now_iso(),
        }

        with self.connection() as conn:
            conn.execute(
                """
                UPDATE users
                SET role = ?, is_active = ?, display_name = ?, updated_at = ?
                WHERE id = ?
                """,
                (updates["role"], updates["is_active"], updates["display_name"], updates["updated_at"], user_id),
            )
            if password:
                conn.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (self._hash_password(password), utc_now_iso(), user_id),
                )
            if is_active is False:
                conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))

        updated = self.get_user_by_id(user_id)
        if updated is None:
            raise AuthError("用户更新失败。")
        return updated


auth_store = AuthStore()
