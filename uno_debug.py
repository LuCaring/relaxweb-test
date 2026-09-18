"""最小化 UNO 时序调试：2 客户端，打印每个原始帧的到达时间。"""
import asyncio
import datetime
import json

import websockets

URI = "ws://localhost:8765"


def now():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


async def client(name):
    ws = await websockets.connect(URI + "/?client=game")
    frames = asyncio.Queue()

    async def reader():
        async for raw in ws:
            data = json.loads(raw)
            desc = ""
            if data.get("type") == "game_update":
                desc = (f"to_act={data.get('to_act')} status={data.get('status')} "
                        f"hand_no={data.get('hand_no')} "
                        f"opts={data.get('your_options')}")
            print(f"  RX[{name}] {now()} {data.get('type')} {desc}", flush=True)
            await frames.put(data)

    asyncio.ensure_future(reader())

    async def send(d):
        print(f"  TX[{name}] {now()} {d.get('type')} {d.get('action','')}", flush=True)
        await ws.send(json.dumps(d, ensure_ascii=False))

    return ws, frames, send


async def expect(frames, want, timeout=6):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        try:
            data = await asyncio.wait_for(frames.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        if data.get("type") in want:
            return data
    return None


async def main():
    ws_a, fa, send_a = await client("A=玩家1")
    ws_b, fb, send_b = await client("B=玩家2")
    for send, name in ((send_a, "玩家1"), (send_b, "玩家2")):
        await send({"type": "login", "username": name, "password": "test123456"})
        await expect(fa if name == "玩家1" else fb, {"login_success"})

    # 清场
    for send, frames in ((send_a, fa), (send_b, fb)):
        await send({"type": "get_room"})
        msg = await expect(frames, {"game_update", "room_closed"})
        if msg and msg["type"] == "game_update":
            await send({"type": "leave_room"})
            await expect(frames, {"room_closed"})

    await send_a({"type": "create_room", "game": "uno", "name": "调试",
                  "buy_in": 100, "blind": 5})
    msg = await expect(fa, {"game_joined"})
    rid = msg["room"]["room_id"]
    await send_b({"type": "join_room", "room_id": rid})
    await expect(fb, {"game_joined"})

    print("== start_game ==", flush=True)
    await send_a({"type": "start_game"})
    # 双方各等 3 秒收帧（不消费 B 后的帧——模拟真实驱动）
    await asyncio.sleep(3)

    print("== A 手动行动循环（30 秒观察窗口）==", flush=True)
    end = asyncio.get_event_loop().time() + 30
    acted_draw = False
    while asyncio.get_event_loop().time() < end:
        data = None
        try:
            data = fa.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
            continue
        if data.get("type") != "game_update":
            continue
        if data.get("to_act") == "玩家1" and data.get("your_options"):
            opts = data["your_options"]
            if opts.get("uno"):
                await send_a({"type": "poker_action", "action": "uno"})
            elif opts.get("draw") and not acted_draw:
                acted_draw = True
                await send_a({"type": "poker_action", "action": "draw"})
            elif opts.get("pass"):
                await send_a({"type": "poker_action", "action": "pass"})
            elif opts.get("draw"):
                await send_a({"type": "poker_action", "action": "draw"})
    print("== done ==", flush=True)
    await ws_a.close()
    await ws_b.close()


asyncio.run(main())
