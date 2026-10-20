"""Real browser regression against an isolated server/database. Uses installed Chrome."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "test-results"
OUTPUT.mkdir(exist_ok=True)
database = OUTPUT / f"browser-{uuid4().hex}.db"
database_url = os.environ.get("BROWSER_TEST_DATABASE_URL")
if database_url:
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").startswith("studyflow_test_"):
        raise RuntimeError("Browser tests require an isolated studyflow_test_* database.")
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
base = f"http://127.0.0.1:{port}"
environment = {
    **os.environ,
    "DATABASE_URL": database_url or "sqlite:///" + database.as_posix(),
    "AI_API_KEY": "",
    "EMBEDDING_API_KEY": "",
}
log = (OUTPUT / "browser-server.log").open("w", encoding="utf-8")
if database_url:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=environment,
        stdout=log,
        stderr=log,
        check=True,
    )
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
    cwd=ROOT,
    env=environment,
    stdout=log,
    stderr=log,
)
errors = []
try:
    for _ in range(100):
        try:
            if urlopen(base + "/health", timeout=1).status == 200:
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("Server did not start; inspect test-results/browser-server.log")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        page.get_by_role("button", name="创建一个", exact=True).click()
        page.get_by_label("怎么称呼你").fill("学习者")
        page.get_by_label("邮箱", exact=True).fill("browser@example.com")
        page.get_by_label("密码", exact=True).fill("browser-test-pass")
        page.get_by_role("button", name="创建账户", exact=True).click()
        expect(page.get_by_role("heading", name="接下来的小目标")).to_be_visible()
        page.get_by_role("link", name="计划与任务", exact=True).click()
        page.get_by_role("button", name="载入示例资料", exact=True).click()
        expect(page.get_by_role("heading", name="构建我的第一个 AI 学习助手")).to_be_visible()
        page.get_by_role("button", name="完成任务", exact=True).first.click()
        expect(page.get_by_role("button", name="取消完成", exact=True)).to_have_count(1)
        page.get_by_role("link", name="学习概览", exact=True).click()
        expect(page.get_by_role("heading", name="接下来的小目标")).to_be_visible()
        page.locator("#toast").evaluate("element => element.classList.remove('show')")
        page.screenshot(path=str(OUTPUT / "dashboard.png"), full_page=True)
        page.get_by_role("button", name="记录今日成长", exact=True).click()
        expect(page.get_by_role("button", name="今日已打卡", exact=True)).to_be_visible()
        page.get_by_role("link", name="知识库", exact=True).click()
        page.get_by_label("回答依据", exact=True).select_option(label="FastAPI 学习手册 · 示例")
        page.get_by_role("textbox", name="知识库问题", exact=True).fill("FastAPI 如何隔离用户数据？")
        page.get_by_role("button", name="提问", exact=True).click()
        expect(page.locator("#answer-text")).to_contain_text("未调用语言模型")
        expect(page.locator(".source")).not_to_have_count(0)
        page.screenshot(path=str(OUTPUT / "knowledge.png"), full_page=True)
        page.get_by_role("link", name="AI 学习教练", exact=True).click()
        page.get_by_role("textbox", name="学习目标", exact=True).fill("学习 RAG 并制作项目演示")
        page.get_by_role("button", name="生成学习计划", exact=False).click()
        expect(page.get_by_role("button", name="确认并创建计划", exact=True)).to_be_visible()
        page.locator("#toast").evaluate("element => element.classList.remove('show')")
        page.screenshot(path=str(OUTPUT / "agent.png"), full_page=True)
        page.get_by_role("button", name="确认并创建计划", exact=True).click()
        expect(page.get_by_role("link", name="查看已创建的计划", exact=False)).to_be_visible()
        page.get_by_role("link", name="专注空间", exact=True).click()
        page.get_by_label("专注时长").select_option("1")
        page.get_by_role("button", name="开始专注", exact=True).click()
        expect(page.get_by_role("button", name="结束本次", exact=True)).to_be_visible()
        page.reload()
        expect(page.get_by_role("button", name="结束本次", exact=True)).to_be_visible()
        page.get_by_role("button", name="结束本次", exact=True).click()
        page.get_by_role("button", name="确认", exact=True).click()
        expect(page.get_by_role("button", name="开始专注", exact=True)).to_be_visible()
        page.get_by_role("link", name="学习广场", exact=True).click()
        expect(page.locator("#online-label")).to_contain_text("在线")
        page.get_by_role("textbox", name="聊天消息", exact=True).fill("<img src=x onerror=alert(1)> 已完成学习")
        page.get_by_role("button", name="发送", exact=True).click()
        expect(page.locator(".chat-bubble")).to_contain_text("<img src=x onerror=alert(1)>")
        assert page.locator(".chat-bubble img").count() == 0
        page.get_by_role("link", name="成长记录", exact=True).click()
        expect(page.get_by_role("heading", name="学习日历")).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("link", name="学习概览", exact=True).click()
        expect(page.get_by_role("heading", name="接下来的小目标")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile horizontal overflow"
        page.screenshot(path=str(OUTPUT / "mobile.png"), full_page=True)
        for name in ["计划与任务", "知识库", "AI 学习教练", "专注空间", "学习广场"]:
            page.get_by_role("link", name=name, exact=True).click()
            page.wait_for_timeout(250)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Mobile overflow on {name}"
        browser.close()
    assert not errors, errors
    print(json.dumps({"status": "passed", "javascript_errors": errors, "screenshots": str(OUTPUT)}, ensure_ascii=False))
finally:
    server.terminate()
    server.wait(timeout=10)
    log.close()
    # Keep the isolated database with other ignored test artifacts for debugging.
