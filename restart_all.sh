#!/bin/bash
# 一键重启全部服务（chat / web / auth），用于本地联调与测试。
#
# 与 reset.sh 的分工：
#   reset.sh      —— 清库、重建测试账号，只重启 chat_server；
#   restart_all.sh—— 不动任何数据，把三个服务一起重启。
# 后端代码改动后跑本脚本，三个服务都会用新代码起来（MediaMTX 是外部服务，不在其中）。
#
# 用法：bash live-test/restart_all.sh（在任意目录下执行都可以）
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
DB="$DIR/users.db"

# 端口按项目自己的规则解析（环境变量 > config.json > 默认值），与三个服务启动时一致，
# 所以改了 config.json 里的端口，这里也跟着变。
read -r CHAT_PORT WEB_PORT AUTH_PORT < <(cd "$ROOT" && python3 -c "
from config import get_int
print(get_int('servers.chat_port', env='LIVE_CHAT_PORT', default=8765),
      get_int('servers.web_port', env='LIVE_WEB_PORT', default=8000),
      get_int('servers.auth_port', env='LIVE_AUTH_PORT', default=8001))
")
if [ -z "$CHAT_PORT" ] || [ -z "$WEB_PORT" ] || [ -z "$AUTH_PORT" ]; then
    echo "解析不出端口，先检查 config.json 与 python3 是否可用" >&2
    exit 1
fi

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# 残留进程会占着端口或继续跑改动前的代码，观察到的一切都会失真，先清干净
pkill -9 -f "chat_server.py" 2>/dev/null || true
pkill -9 -f "deploy/serve.py" 2>/dev/null || true
pkill -9 -f "auth_server.py" 2>/dev/null || true
sleep 0.5

# 端口必须真的空出来，否则新进程绑不上，后面的就绪检测会被旧进程骗过去
busy=""
for spec in "chat:$CHAT_PORT" "web:$WEB_PORT" "auth:$AUTH_PORT"; do
    if port_open "${spec#*:}"; then busy="$busy ${spec%%:*}(${spec#*:})"; fi
done
if [ -n "$busy" ]; then
    echo "端口仍被占用:$busy —— 可能有残留进程没清掉，先处理再重试" >&2
    exit 1
fi

fail=0
wait_port() {  # wait_port <pgrep 模式> <端口> <日志>
    local pattern="$1" port="$2" log="$3" i
    for i in $(seq 1 40); do
        if port_open "$port"; then
            printf '  ✔ %-20s :%-5s pid=%-7s %s\n' "$pattern" "$port" "$(pgrep -f "$pattern" | tail -1)" "$log"
            return 0
        fi
        sleep 0.25
    done
    printf '  ✘ %-20s :%-5s 10 秒内未监听，见 %s\n' "$pattern" "$port" "$log"
    return 1
}

echo "重启本地测试服务（数据不动，库 $DB）:"
cd "$ROOT"
# chat_server 用测试库；web/auth 按默认配置起（与 prod 的部署方式一致）
# 起完就 disown：否则下一轮 pkill 掉它们时，本 shell 会打出「已杀死」的作业通知
setsid nohup env LIVE_DB_FILE="$DB" python3 chat_server.py > "$DIR/chat.log" 2>&1 < /dev/null &
disown
wait_port "chat_server.py" "$CHAT_PORT" "chat.log" || fail=1

setsid nohup python3 deploy/serve.py > "$DIR/web.log" 2>&1 < /dev/null &
disown
wait_port "deploy/serve.py" "$WEB_PORT" "web.log" || fail=1

setsid nohup python3 auth_server.py > "$DIR/auth.log" 2>&1 < /dev/null &
disown
wait_port "auth_server.py" "$AUTH_PORT" "auth.log" || fail=1

if [ "$fail" -ne 0 ]; then
    echo "有服务没起来。" >&2
    exit 1
fi
echo "全部就绪：游戏页 http://localhost:$WEB_PORT/game.html"
