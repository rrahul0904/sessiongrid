import asyncio
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from app.config import settings


@dataclass
class ActiveRuntime:
    profile_id: int
    context: BrowserContext
    page: Page


class RuntimeManager:
    """Local MVP runtime.

    Production replaces this in-process manager with a durable orchestrator
    and isolated worker pool. The interface is intentionally small so browser,
    Android and remote-device providers can share the same control contract.
    """

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._runtimes: dict[int, ActiveRuntime] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._playwright is None:
            self._playwright = await async_playwright().start()

    async def close(self) -> None:
        async with self._lock:
            for runtime in list(self._runtimes.values()):
                try:
                    await runtime.context.close()
                except Exception:
                    pass
            self._runtimes.clear()
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def launch(
        self,
        *,
        profile_id: int,
        start_url: str,
        locale: str,
        timezone: str,
    ) -> ActiveRuntime:
        await self.start()
        async with self._lock:
            if profile_id in self._runtimes:
                return self._runtimes[profile_id]

            assert self._playwright is not None
            profile_dir = Path(settings.runtime_path) / f"profile-{profile_id}"
            profile_dir.mkdir(parents=True, exist_ok=True)

            context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=settings.headless,
                viewport={"width": 430, "height": 820},
                locale=locale,
                timezone_id=timezone,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(start_url, wait_until="domcontentloaded", timeout=30000)

            runtime = ActiveRuntime(profile_id=profile_id, context=context, page=page)
            self._runtimes[profile_id] = runtime
            return runtime

    async def stop(self, profile_id: int) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(profile_id, None)
        if runtime:
            await runtime.context.close()

    def get(self, profile_id: int) -> ActiveRuntime | None:
        return self._runtimes.get(profile_id)

    async def screenshot(self, profile_id: int) -> bytes:
        runtime = self.get(profile_id)
        if not runtime:
            raise RuntimeError("Runtime is not active")
        return await runtime.page.screenshot(
            type="jpeg",
            quality=settings.screenshot_quality,
            full_page=False,
        )

    async def pointer(self, profile_id: int, x: float, y: float) -> None:
        runtime = self.get(profile_id)
        if not runtime:
            raise RuntimeError("Runtime is not active")
        await runtime.page.mouse.click(x, y)

    async def text(self, profile_id: int, text: str) -> None:
        runtime = self.get(profile_id)
        if not runtime:
            raise RuntimeError("Runtime is not active")
        await runtime.page.keyboard.insert_text(text)

    async def state(self, profile_id: int) -> tuple[str | None, str | None]:
        runtime = self.get(profile_id)
        if not runtime:
            return None, None
        title = await runtime.page.title()
        return runtime.page.url, title


runtime_manager = RuntimeManager()
