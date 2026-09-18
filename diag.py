import asyncio
import json

import websockets

URI = "ws://localhost:8765"


async def make_cli():
    ws = await websockets.connect(URI)
    q = asyncio.Queue()

    async def reader():
        try:
            async for raw in ws:
                await q.put(raw.decode() if isinstance(raw, bytes) else raw)
        except Exception as e:
            await q.put(f"__READER_DIED__ {e!r}")

    t = asyncio.ensure_future(reader())

    async def send(d):
        await ws.send(json.dumps(d, ensure_ascii=False))

    async def recv(want, timeout=5):
        try:
            while True:
                raw = await asyncio.wait_for(q.get(), timeout)
                data = json.loads(raw)
                if data.get("type") in want:
                    return data
        except asyncio.TimeoutError:
            return None

    return {"ws": ws, "send": send, "recv": recv, "q": q, "task": t}


async def main():
    c1 = await make_cli()
    await c1["send"]({"type": "login", "username": "玩家1", "password": "test123456"})
    await c1["recv"]({"login_success"})
    await c1["send"]({"type": "create_room", "name": "诊断", "buy_in": 100, "blind": 5})
    await c1["recv"]({"game_joined"})
    print("room created", flush=True)

    c2 = await make_cli()
    await c2["send"]({"type": "login", "username": "玩家2", "password": "test123456"})
    await c2["recv"]({"login_success"})
    await c2["send"]({"type": "join_room"})
    # join needs room id: use list first
    c2b = None
    # simpler: get room id from c1's room_list broadcast
    rl = await c1["recv"]({"room_list"})
    room_id = rl["rooms"][0]["id"] if rl and rl["rooms"] else None
    print("room_id =", room_id, flush=True)
    if room_id:
        await c2["send"]({"type": "join_room", "room_id": room_id})
        j = await c2["recv"]({"game_joined"})
        print("c2 joined:", bool(j), flush=True)
        w = await c1["recv"]({"game_update"})
        print("c1 got waiting view:", bool(w), flush=True)

        await c2["send"]({"type": "start_game"})
        got = []
        try:
            while True:
                raw = await asyncio.wait_for(c1["q"].get(), 4)
                data = json.loads(raw)
                got.append((data.get("type"), data.get("stage"), data.get("to_act")))
        except asyncio.TimeoutError:
            pass
        print("c1 messages after start_game:", got, flush=True)

        await c1["send"]({"type": "get_room"})
        raw = None
        try:
            raw = await asyncio.wait_for(c1["q"].get(), 4)
        except asyncio.TimeoutError:
            pass
        print("c1 get_room direct reply:", (json.loads(raw).get("type"),
              json.loads(raw).get("stage")) if raw else "NONE", flush=True)


asyncio.run(main())
