"""集成冒烟测试：claude CLI 日志分析 + multica 模板适配（真实调用，不入库）。"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.init_db import init_db
from app.services import multica
from app.services.analyzer import analyze_logs

SAMPLE_LOG = """2026-08-25T10:00:00.123456789Z INFO  app started on port 8000
2026-08-25T10:00:05.000000000Z GET /api/users 200 12ms
2026-08-25T10:00:09.000000000Z GET /api/orders/42 500 88ms
2026-08-25T10:00:09.001000000Z Traceback (most recent call last):
2026-08-25T10:00:09.001000000Z   File "/app/services/orders.py", line 42, in get_order
2026-08-25T10:00:09.001000000Z     price = order["total_price"] / order["item_count"]
2026-08-25T10:00:09.001000000Z ZeroDivisionError: division by zero
2026-08-25T10:00:10.000000000Z GET /health 200 1ms
"""


async def main() -> None:
    await init_db()

    # 1. multica 模板适配：用 echo 模拟真实 CLI 输出
    from app.services import settings_service

    await settings_service.update_settings(
        {"multica.create_cmd": 'echo "Created task, ID: MC-777"'}
    )
    task_id, output = await multica.create_task("[auto] test", "desc")
    assert task_id == "MC-777", f"multica ID 提取失败: {task_id!r} output={output!r}"
    print(f"[ok] multica 适配器提取到任务 ID: {task_id}")

    # 2. claude CLI 日志分析
    result = await analyze_logs(SAMPLE_LOG, "demo-api", "https://jihulab.com/demo/demo-api")
    print(f"[ok] AI 分析: has_error={result.has_error} type={result.error_type}")
    print(f"     message={result.message}")
    print(f"     fingerprint={result.fingerprint}")
    print(f"     suspects={result.suspect_files}")
    assert result.has_error, "应当识别出错误"
    assert result.fingerprint, "应当给出错误指纹"

    await SessionLocal().close() if False else None
    from app.database import engine

    await engine.dispose()
    print("[done] 集成冒烟测试全部通过")


asyncio.run(main())
