#!/usr/bin/env python3
"""
launchs-org セットアップウィザード
secret.yaml / postgresql-secret.yaml / temporal-secret.yaml を生成します。
kubectl apply は行いません。
"""

import base64
import os
import secrets
import shutil
import string
import sys


# ── ターミナルカラー ──────────────────────────────────────────
class C:
    BOLD  = "\033[1m"
    CYAN  = "\033[96m"
    GREEN = "\033[92m"
    YELLOW= "\033[93m"
    RED   = "\033[91m"
    RESET = "\033[0m"


def title(text: str) -> None:
    print(f"\n{C.BOLD}{C.CYAN}{'─' * 60}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  {text}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'─' * 60}{C.RESET}\n")


def section(text: str) -> None:
    print(f"\n{C.BOLD}{C.YELLOW}▶ {text}{C.RESET}")


def ok(text: str) -> None:
    print(f"{C.GREEN}✔ {text}{C.RESET}")


def warn(text: str) -> None:
    print(f"{C.YELLOW}⚠ {text}{C.RESET}")


# ── 入力ヘルパー ──────────────────────────────────────────────
def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    """標準入力で値を取得する。secret=True のとき入力をエコーバックしない。"""
    hint = f" [{default}]" if default else ""
    full = f"  {prompt}{hint}: "
    if secret:
        import getpass
        val = getpass.getpass(full)
    else:
        print(full, end="", flush=True)
        val = sys.stdin.readline().rstrip("\n")
    return val if val else default


def confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    ans = ask(f"{prompt} ({hint})").strip().lower()
    if ans == "":
        return default
    return ans in ("y", "yes")


# ── パスワード生成 ────────────────────────────────────────────
def gen_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def gen_token(length: int = 64) -> str:
    return secrets.token_urlsafe(length)


def b64enc(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


# ── テンプレート置換 ──────────────────────────────────────────
def render_template(template_path: str, values: dict[str, str]) -> str:
    with open(template_path) as f:
        content = f.read()
    for key, value in values.items():
        # stringData の場合: key: "" → key: "value"
        content = content.replace(f'  {key}: ""', f'  {key}: "{value}"')
        # data (base64) の場合: password: "" → password: <base64>
        content = content.replace(f'  password: ""', f'  password: {value}') if key == "password" else content
    return content


def write_file(path: str, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)
    ok(f"生成: {path}")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve(filename: str) -> str:
    return os.path.join(SCRIPT_DIR, filename)


# ═══════════════════════════════════════════════════════════════
# ウィザード本体
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    title("launchs-org セットアップウィザード")
    print("  各シークレットファイルを生成します。")
    print("  パスワードは自動生成されます（手動入力も可）。")
    print("  生成されたファイルは .gitignore に含まれており、git にはコミットされません。\n")

    # ── 既存ファイルの確認 ────────────────────────────────────
    targets = ["secret.yaml", "postgresql-secret.yaml", "temporal-secret.yaml"]
    existing = [t for t in targets if os.path.exists(resolve(t))]
    if existing:
        warn(f"既存ファイルが見つかりました: {', '.join(existing)}")
        if not confirm("上書きしますか？", default=False):
            print("  中断しました。")
            sys.exit(0)

    # ════════════════════════════════════════════════════════════
    # 1. PostgreSQL 接続情報
    # ════════════════════════════════════════════════════════════
    section("1. PostgreSQL 接続情報")
    pg_host = ask("PostgreSQL ホスト名", "launchs-org-database-cluster.launchs-org")
    pg_port = ask("PostgreSQL ポート", "5432")

    # ユーザーごとのパスワード生成
    print()
    warn("各 PostgreSQL ユーザーのパスワードを設定します（Enter で自動生成）")

    main_pass  = ask("main ユーザーのパスワード") or gen_password()
    task_pass  = ask("task_user ユーザーのパスワード") or gen_password()
    auth_pass  = ask("auth ユーザーのパスワード") or gen_password()
    temp_pass  = ask("temporal ユーザーのパスワード") or gen_password()

    # DB 接続文字列
    database_dsn      = f"host={pg_host} port={pg_port} sslmode=disable TimeZone=Asia/Tokyo user=main password={main_pass} dbname=maindb"
    task_database_dsn = f"host={pg_host} port={pg_port} sslmode=disable user=task_user password={task_pass} dbname=taskdb"
    db_dsn            = f"host={pg_host} port={pg_port} sslmode=disable TimeZone=Asia/Tokyo user=auth password={auth_pass} dbname=authdb"

    # ════════════════════════════════════════════════════════════
    # 2. Harbor レジストリ
    # ════════════════════════════════════════════════════════════
    section("2. Harbor レジストリ")
    harbor_host     = ask("Harbor ホスト名", "harbor.main-harbor")
    harbor_url      = ask("Harbor URL", f"https://{harbor_host}")
    harbor_username = ask("Harbor ユーザー名 (builder 用)")
    harbor_password = ask("Harbor パスワード (builder 用)", secret=True)
    harbor_admin_user     = ask("Harbor 管理者ユーザー名 (controller 用)")
    harbor_admin_password = ask("Harbor 管理者パスワード (controller 用)", secret=True)

    # ════════════════════════════════════════════════════════════
    # 3. Backend セッションシークレット
    # ════════════════════════════════════════════════════════════
    section("3. Backend")
    session_secret = ask("SessionSecret（Enter で自動生成）") or gen_token(48)

    # ════════════════════════════════════════════════════════════
    # 4. Auth サービス
    # ════════════════════════════════════════════════════════════
    section("4. Auth サービス — OAuth 設定")
    print("  ※ 使用しないプロバイダーは空欄のままにしてください\n")

    discord_client_id     = ask("Discord Client ID")
    discord_client_secret = ask("Discord Client Secret", secret=True)
    discord_callback      = ask("Discord Callback URL", "https://www.launchs.org/auth/oauth/discord/callback")

    google_client_id      = ask("Google Client ID")
    google_client_secret  = ask("Google Client Secret", secret=True)
    google_callback       = ask("Google Callback URL", "https://www.launchs.org/auth/oauth/google/callback")

    github_client_id      = ask("GitHub Client ID")
    github_client_secret  = ask("GitHub Client Secret", secret=True)
    github_callback       = ask("GitHub Callback URL", "https://www.launchs.org/auth/oauth/github/callback")

    microsoft_client_id     = ask("Microsoft Client ID")
    microsoft_client_secret = ask("Microsoft Client Secret", secret=True)
    microsoft_callback      = ask("Microsoft Callback URL", "https://www.launchs.org/auth/oauth/microsoftonline/callback")

    section("4. Auth サービス — 管理者・JWT")
    admin_email       = ask("管理者メールアドレス", "admin@example.com")
    admin_password    = ask("管理者パスワード（平文、bcrypt ハッシュはアプリ側で生成）", secret=True) or gen_password(24)
    token_secret      = ask("TOKEN_SECRET（Enter で自動生成）") or gen_token(48)
    admin_session_key = ask("ADMIN_SESSION_KEY（Enter で自動生成）") or gen_token(48)

    section("4. Auth サービス — JWT 鍵ペア")
    print("  Ed25519 の PEM 形式の鍵を貼り付けてください。")
    print("  鍵を持っていない場合は以下で生成できます:")
    print("    openssl genpkey -algorithm ed25519 -out private.pem")
    print("    openssl pkey -in private.pem -pubout -out public.pem\n")

    print("  JWT_PRIVATE_KEY (PEM, 複数行可。入力後に空行 + Enter):")
    jwt_private_lines = []
    while True:
        line = sys.stdin.readline().rstrip("\n")
        if line == "":
            break
        jwt_private_lines.append(line)
    jwt_private_key = "\n".join(jwt_private_lines)

    print("  JWT_PUBLIC_KEY (PEM, 複数行可。入力後に空行 + Enter):")
    jwt_public_lines = []
    while True:
        line = sys.stdin.readline().rstrip("\n")
        if line == "":
            break
        jwt_public_lines.append(line)
    jwt_public_key = "\n".join(jwt_public_lines)

    # ════════════════════════════════════════════════════════════
    # ファイル生成
    # ════════════════════════════════════════════════════════════
    title("ファイルを生成しています...")

    # ── secret.yaml ──────────────────────────────────────────
    secret_values = {
        "SessionSecret":        session_secret,
        "DATABASE_DSN":         database_dsn,
        "TASK_DATABASE_DSN":    task_database_dsn,
        "DiscordClientID":      discord_client_id,
        "DiscordClientSecret":  discord_client_secret,
        "DiscordCallback":      discord_callback,
        "GoogleClientID":       google_client_id,
        "GoogleClientSecret":   google_client_secret,
        "GoogleCallback":       google_callback,
        "GithubClientID":       github_client_id,
        "GithubClientSecret":   github_client_secret,
        "GithubCallback":       github_callback,
        "MicrosoftClientID":    microsoft_client_id,
        "MicrosoftClientSecret":microsoft_client_secret,
        "MicrosoftCallback":    microsoft_callback,
        "AdminEmail":           admin_email,
        "AdminPassword":        admin_password,
        "DB_DSN":               db_dsn,
        "TOKEN_SECRET":         token_secret,
        "ADMIN_SESSION_KEY":    admin_session_key,
        "JWT_PRIVATE_KEY":      jwt_private_key,
        "JWT_PUBLIC_KEY":       jwt_public_key,
        "HARBOR_URL":           harbor_url,
        "HARBOR_REGISTRY":      harbor_host,
        "HARBOR_USERNAME":      harbor_username,
        "HARBOR_PASSWORD":      harbor_password,
        "HARBOR_ADMIN_USER":    harbor_admin_user,
        "HARBOR_ADMIN_PASSWORD":harbor_admin_password,
    }

    with open(resolve("secret.yaml_template")) as f:
        secret_content = f.read()

    for key, value in secret_values.items():
        # PEM 鍵はブロックスカラー形式に変換
        if key in ("JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY") and "\n" in value:
            indented = "\n".join(f"    {line}" for line in value.splitlines())
            secret_content = secret_content.replace(
                f'  {key}: ""',
                f'  {key}: |\n{indented}'
            )
        else:
            escaped = value.replace('"', '\\"')
            secret_content = secret_content.replace(f'  {key}: ""', f'  {key}: "{escaped}"')

    write_file(resolve("secret.yaml"), secret_content)

    # ── postgresql-secret.yaml ────────────────────────────────
    with open(resolve("postgresql-secret.yaml_template")) as f:
        pg_content = f.read()

    # Zalando オペレーター用: data フィールドは base64
    pg_passwords = {
        "main":     main_pass,
        "task_user":task_pass,
        "auth":     auth_pass,
        "temporal": temp_pass,
    }

    # テンプレート内の password: "" を各ユーザーの base64 値に置き換える
    # ユーザー名ブロック単位で置換するため、ユーザー名のコンテキストで処理
    lines = pg_content.splitlines()
    out_lines = []
    current_user = None
    for line in lines:
        if "username:" in line:
            # username の base64 からユーザー名を特定
            b64val = line.split("username:")[-1].strip()
            try:
                current_user = base64.b64decode(b64val).decode()
            except Exception:
                current_user = None
        if line.strip() == 'password: ""' and current_user in pg_passwords:
            b64pass = b64enc(pg_passwords[current_user])
            out_lines.append(line.replace('""', b64pass))
            current_user = None
            continue
        out_lines.append(line)

    write_file(resolve("postgresql-secret.yaml"), "\n".join(out_lines))

    # ════════════════════════════════════════════════════════════
    # 完了メッセージ
    # ════════════════════════════════════════════════════════════
    title("セットアップ完了")
    print("  生成されたファイル:")
    print("    - secret.yaml")
    print("    - postgresql-secret.yaml")
    print("  次のステップ:")
    print("    1. kubectl create ns launchs-org")
    print("    2. kubectl apply -k .")
    print("    3. kubectl apply -f ./network-policy-harbor.yaml")
    print("    4. kubectl apply -f ./rbac-builder.yaml")
    print("    5. helm install --repo https://go.temporal.io/helm-charts -f temporal-values.yaml temporal temporal --timeout 900s --debug --namespace launchs-org\n")
    warn("これらのファイルは .gitignore に含まれています。git にコミットしないよう注意してください。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  中断しました。")
        sys.exit(1)
