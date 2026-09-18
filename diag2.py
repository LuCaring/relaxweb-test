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
                data = json.loads(raw)
                print(f"  [{name} {time.strftime('%H:%M:%S')}] <- {data.get('type')}", flush=True)
                await q.put(data)
        except Exception as e:
            print(f"  [{name}] reader died: {e!r}", flush=True)

    t = asyncio.ensure_future(reader())

    async def send(d):
        print(f"  [{name}] -> {d.get('type')} {d.get('room_id', '')}", flush=True)
        await ws.send(json.dumps(d, ensure_ascii=False))

    async def recv(types, timeout=5):
        try:
            while True:
                data = await asyncio.wait_for(q.get(), timeout)
                if data.get("type") in types:
                    return data
        except asyncio.TimeoutError:
            return None

    return {"ws": ws, "send": send, "recv": recv, "task": t}


async def main():
    c1 = await make_cli("c1")
    await c1["send"]({"type": "login", "username": "玩家1", "password": "test123456"})
    await c1["recv"]({"login_success"})
    await c1["send"]({"type": "create_room", "name": "诊断2", "buy_in": 100, "blind": 5})
    j = await c1["recv"]({"game_joined"})
    room_id = j["room"]["room_id"]
    rl = await c1["recv"]({"room_list"})
    print("room ready:", room_id, "room_list:", bool(rl), flush=True)

    c2 = await make_cli("c2")
    await c2["send"]({"type": "login", "username": "玩家2", "password": "test123456"})
    lg = await c2["recv"]({"login_success"})
    print("c2 login:", bool(lg), flush=True)

    await c2["send"]({"type": "get_finance"})
    fin = await c2["recv"]({"finance"})
    print("c2 finance roundtrip:", bool(fin), f"coins={fin and fin['coins']}", flush=True)

    await c2["send"]({"type": "join_room", "room_id": room_id})
    msg = await c2["recv"]({"game_joined", "game_error"})
    print("c2 join result:", msg and msg.get("type"), (msg or {}).get("message", ""), flush=True)

    msg = await c1["recv"]({"game_update", "room_list"}, timeout=5)
    print("c1 after-join recv:", msg and msg.get("type"), flush=True)


asyncio.run(main())
