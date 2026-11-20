"""Per-worker Chromium state, serialized actions, and cleanup."""

import asyncio
import base64
import os

from fastapi import HTTPException
from playwright.async_api import async_playwright

from loop_sandbox.contracts.models import BrowserAction

browser_lock = asyncio.Lock()


async def close_browser(state):
    if getattr(state, "browser", None):
        await state.browser.close()
    if getattr(state, "pw", None):
        await state.pw.stop()


async def run_browser(state, body: BrowserAction):
    async with browser_lock:
        if not getattr(state, "browser", None) or not state.browser.is_connected():
            if getattr(state, "pw", None):
                await state.pw.stop()
            state.pw = await async_playwright().start()
            state.browser = await state.pw.chromium.launch(
                headless=True, executable_path=os.getenv("CHROMIUM_EXECUTABLE")
            )
            state.page = await state.browser.new_page()
            state.page.set_default_timeout(10000)
        page = state.page
        if body.action == "open":
            if not body.url or not body.url.startswith(("http://", "https://")):
                raise HTTPException(400, "HTTP(S) URL required")
            await page.goto(body.url, wait_until="domcontentloaded", timeout=20000)
        elif body.action == "set_content":
            await page.set_content(body.text or "", wait_until="domcontentloaded")
        elif body.action == "click":
            if not body.selector:
                raise HTTPException(400, "selector required")
            await page.locator(body.selector).click()
        elif body.action == "fill":
            if not body.selector:
                raise HTTPException(400, "selector required")
            await page.locator(body.selector).fill(body.text or "")
        elif body.action == "screenshot":
            data = await page.screenshot(full_page=False)
            return {"mime_type": "image/png", "base64": base64.b64encode(data).decode()}
        elif body.action != "snapshot":
            raise HTTPException(400, "Unknown browser action")
        return {
            "url": page.url,
            "title": await page.title(),
            "text": (await page.locator("body").inner_text())[:12000],
        }
