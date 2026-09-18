#!/bin/bash
# 重置本地测试环境：清库、重建测试账号、重启 chat_server
# 用法：bash live-test/reset.sh（在任意目录下执行都可以）
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
DB="$DIR/users.db"
LOG="$DIR/chat.log"

# 先清掉可能残留的旧进程（含沙箱自动重启的幽灵进程），避免它占着 8765 或改错库
pkill -9 -f "chat_server.py" 2>/dev/null || true
sleep 0.5
rm -f "$DB"
cd "$ROOT"
LIVE_DB_FILE="$DB" python3 - <<'EOF'
import os, sqlite3, time
import chat_server as cs

db = os.environ["LIVE_DB_FILE"]
cs.init_db()
conn = sqlite3.connect(db)
for i in range(1, 6):
    conn.execute(
        "INSERT OR IGNORE INTO invite_codes (code, created_at, created_by) VALUES (?, ?, 'seed')",
        (f"TESTCODE{i}", int(time.time())),
    )
conn.commit()
conn.close()
for i in (1, 2, 3):
    cs.register_user(f"玩家{i}", "test123456", f"TESTCODE{i}")
print("seeded")
EOF
setsid nohup env LIVE_DB_FILE="$DB" python3 chat_server.py > "$LOG" 2>&1 < /dev/null &
disown
for i in $(seq 1 20); do grep -q "listening on ws" "$LOG" && break; sleep 0.5; done
echo "server ready: $(tail -1 "$LOG")"
