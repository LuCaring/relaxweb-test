# live-test · 本地联调与协议测试

live-web 的本地联调环境与测试脚本，独立成一个 git 仓库管理。
所有脚本都打本地 `ws://localhost:8765`，不碰线上数据、不改线上配置。

依赖：`python3` + `websockets`（`python3 -m pip install --user websockets`）。

## 起环境

```bash
bash live-test/reset.sh          # 清库、重建 玩家1/2/3、重启 chat_server(:8765)
python3 deploy/serve.py          # 另开一个终端：静态页 (:8000)
```

浏览器打开 <http://localhost:8000/game.html>，用 `玩家1 / test123456` 登录
（测试账号固定：玩家1、玩家2、玩家3，密码都是 `test123456`）。

`reset.sh` 会先 `pkill -9 -f chat_server.py`，因为残留的旧进程会占着 8765
端口或改到别的库，观察到的一切都会失真。

## 自动化测试

| 脚本 | 覆盖内容 |
| --- | --- |
| `proto_test.py` | 主协议测试（16 项）：登录、建房、开局发牌、暂停恢复、打完一手、房间聊天广播、结算投票再来一局、金币明细、在线计数、断线宽限保座、离桌结算与退款、房主解散退款 |
| `uno_proto_test.py` | UNO 协议测试：建房发牌、三客户端打完一局、结算投票与解散退款 |

```bash
python3 live-test/proto_test.py
```

引擎纯逻辑用例在另一个仓库目录 `tests/test_games.py`（不需要起服务）。

## 陪打机器人

| 脚本 | 行为 |
| --- | --- |
| `bot.py 玩家2` | 通用机器人：登录、自动找房加入、按 check > call > 全下跟注行动 |
| `poker_bot.py 玩家2 [raise]` | 德州机器人：入座、跟注看牌、结算自动投「再来一局」；带 `raise` 参数时每手首次行动会加注一次 |
| `uno_bot.py [玩家2]` | UNO 机器人：入座、事件驱动出牌 |

机器人是长驻进程，配合浏览器手动点操作使用；`pkill -f poker_bot.py` 停掉。

## 排查用脚本

| 脚本 | 用途 |
| --- | --- |
| `settle_verify.py` | 结算投票流程：单票未过半、过半生效、下一手盲注是否按投票调整 |
| `merge_verify.py` | 金币流水合并（净额结算）七个场景：输/赢合并、流局删条目、未开局无痕迹、打完离桌合并、未开局解散 |
| `peek.py <邀请码>` | 注册一个「观察员」账号并打印房间视图（结算字段、每人筹码/下注、result.hands） |
| `diag.py` / `diag2.py` / `diag3.py` | 连接与消息时序诊断（幽灵进程占座、重复 login、建房后视图漏发等一次性排查） |
| `uno_debug.py` | UNO 最小时序调试：两个客户端，打印每帧到达时间 |

这些是排查历史问题留下的脚本，改动协议后按需复用。

## 产物

`users.db`、`*.log`、`*.out`、`__pycache__/` 都是运行时产物，已被 `.gitignore` 忽略。
