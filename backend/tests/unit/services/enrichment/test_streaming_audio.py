"""TTS 流式 tee:一次调用、劈两路、落库扛客户端断连。asyncio mode=auto。"""

import asyncio

from app.services.enrichment.streaming_audio import start_and_stream


async def test_tee_full_consume_single_call():
    calls = []
    persisted = {}

    async def persist(b):
        persisted["b"] = b

    async def src():
        calls.append(1)
        for c in (b"a", b"b", b"c"):
            yield c

    gen = await start_and_stream(src, persist)
    got = b"".join([x async for x in gen])
    await asyncio.sleep(0.02)  # 让 producer 落库
    assert got == b"abc"
    assert persisted["b"] == b"abc"
    assert len(calls) == 1  # 唯一一次 TTS 调用(单次 tee,不双倍费用)


async def test_persist_survives_client_abort():
    calls = []
    done = asyncio.Event()
    persisted = {}

    async def persist(b):
        persisted["b"] = b
        done.set()

    async def slow_src():
        calls.append(1)
        for c in (b"x", b"y", b"z"):
            await asyncio.sleep(0.005)
            yield c

    gen = await start_and_stream(slow_src, persist)
    first = await gen.__anext__()  # 客户端只收一块
    assert first == b"x"
    await gen.aclose()  # 断连/退出
    await asyncio.wait_for(done.wait(), timeout=2)  # producer 仍跑完
    assert persisted["b"] == b"xyz"  # 断连也落全量,不是半截
    assert len(calls) == 1


async def test_error_persists_none_and_releases():
    persisted = {"called": False, "b": b"X"}

    async def persist(b):
        persisted["called"] = True
        persisted["b"] = b

    async def bad_src():
        yield b"a"
        raise RuntimeError("tts died")

    gen = await start_and_stream(bad_src, persist)
    _ = [x async for x in gen]  # 消费到哨兵
    await asyncio.sleep(0.02)
    assert persisted["called"] and persisted["b"] is None  # 失败→释放锁不写key
