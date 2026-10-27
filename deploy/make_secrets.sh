#!/bin/bash
# データベースのパスワードを作って secrets/ に置く（画面には出さない。1回だけ。あれば作り直さない）
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p secrets && chmod 700 secrets
[ -s secrets/db_password ] || (umask 077; python3 -c "import secrets;print(secrets.token_urlsafe(32))" > secrets/db_password)
(umask 077; printf 'postgresql+psycopg://shiwake:%s@db:5432/shiwake\n' "$(cat secrets/db_password)" > secrets/database_url)
# アプリは中で uid 10001 で動くので、接続先のファイルはその人だけが読めるようにする（Linux では持ち主の番号がそのまま中に見える）
[ "$(id -u)" = 0 ] && chown 10001 secrets/database_url
echo "secrets/ を用意しました（中身は表示しません）"
