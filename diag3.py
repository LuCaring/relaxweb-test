"""隔离复现：打完一手后，对已有连接再次发 login 是否有响应。"""
import asyncio
import json
import time

import websockets

URI = "ws://localhost:8765"


async def make_cli(name):
    ws = await websockets.connect(URI)
    q = asyncio.Queue()

    async def reader():
        try:
            async for raw in ws:
                await q.put(raw if isinstance(raw, str) else raw.decode())
        except Exception as e:
            await q.put(json.dumps({"type": "__reader_died__", "error": repr(e)}))

    asyncio.ensure_future(reader())

    async def send(d):
        print(f"  [{name} {time.strftime('%H:%M:%S')}] -> {d.get('type')}", flush=True)
        try:
            await ws.send(json.dumps(d, ensure_ascii=False))
        except Exception as e:
            print(f"  [{name}] SEND FAILED: {e!r}", flush=True)

    async def recv(types, timeout=6):
        while True:
            try:
                raw = await asyncio.wait_for(q.get(), timeout)
            except asyncio.TimeoutError:
                return None
            data = json.loads(raw)
            t = data.get("type")
            if str(t).startswith("__"):
                print(f"  [{name}] READER: {t} {data.get('error', '')}", flush=True)
                continue
            if t in types:
                return data

    return {"ws": ws, "send": send, "recv": recv}


async def drive(cli, who, done):
    while not done.is_set():
        await cli["send"]({"type": "get_room"})
        msg = await cli["recv"]({"game_update", "hand_result", "room_closed"}, timeout=6)
        if msg is None:
            return False
        t = msg["type"]
        if t == "hand_result" or (t == "game_update" and msg.get("result")):
            done.set()
            return True
        if t == "room_closed":
            return False
        if msg.get("to_act") == who:
            opts = msg["your_options"] or {}
            if opts.get("check"):
                await cli["send"]({"type": "poker_action", "action": "check"})
            elif opts.get("call"):
                await cli["send"]({"type": "poker_action", "action": "call"})
            elif opts.get("allin"):
                await cli["send"]({"type": "poker_action", "action": "raise",
                                   "raise_to": opts["allin_to"]})
            else:
                await cli["send"]({"type": "poker_action", "action": "fold"})
    return True


async def main():
    c1 = await make_cli("c1")
    await c1["send"]({"type": "login", "username": "玩家1", "password": "test123456"})
    await c1["recv"]({"login_success"})
    await c1["send"]({"type": "create_room", "name": "隔离", "buy_in": 100, "blind": 5})
    j = await c1["recv"]({"game_joined"})
    room_id = j["room"]["room_id"]
    await c1["recv"]({"room_list"})

    c2 = await make_cli("c2")
    await c2["send"]({"type": "login", "username": "玩家2", "password": "test123456"})
    await c2["recv"]({"login_success"})
    await c2["send"]({"type": "join_room", "room_id": room_id})
    await c2["recv"]({"game_joined"})
    await c1["recv"]({"game_update"})

    await c1["send"]({"type": "start_game"})
    for _ in range(10):
        m = await c1["recv"]({"game_update"})
        if m and m.get("stage") == "preflop":
            break
    print("hand started", flush=True)

    done = asyncio.Event()
    await asyncio.gather(drive(c1, "玩家1", done), drive(c2, "玩家2", done))
    print("hand finished", flush=True)

    await asyncio.sleep(1)
    await c2["send"]({"type": "login", "username": "玩家2", "password": "test123456"})
    msg = await c2["recv"]({"login_success", "auth_error"})
    print("SECOND LOGIN:", msg and msg.get("type"), flush=True)


asyncio.run(main())
