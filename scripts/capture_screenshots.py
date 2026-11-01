"""Captura screenshots atualizados da UI (Copiloto com crew, Painel, Observabilidade).

Uso: ./venv/bin/python scripts/capture_screenshots.py
Requer: app rodando em http://localhost:8501 e Chrome instalado.

Alem de capturar, ASSERTA que os elementos-chave de cada pagina estao visiveis
(rastro da crew aberto, painel renderizado, diario com chamadas) — screenshot
comprovado, nao cego.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

BASE = "http://localhost:8501"
PERGUNTA = "Qual o SLA de correção para uma CVE com CVSS 9.5 em ativo exposto?"


async def capturar(page, caminho: str, deve_conter: list[str]) -> None:
    """Screenshot + prova textual: todos os textos precisam estar na pagina."""
    corpo = (await page.content()).lower()
    faltando = [t for t in deve_conter if t.lower() not in corpo]
    if faltando:
        raise AssertionError(f"{caminho}: nao achei na pagina: {faltando}")
    await page.screenshot(path=caminho, full_page=False)
    print(f"ok {caminho} (verificado: {', '.join(deve_conter)})")


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page(
            viewport={"width": 1512, "height": 960}, device_scale_factor=2
        )

        # ── 1) Copiloto: pergunta real -> resposta -> rastro da crew aberto ──
        await page.goto(BASE, wait_until="domcontentloaded")
        entrada = page.locator("div[data-testid='stChatInput'] textarea")
        await entrada.wait_for(state="visible", timeout=90_000)
        await page.wait_for_timeout(1_800)  # fonts/glow assentam
        await entrada.fill(PERGUNTA)
        await page.wait_for_timeout(400)
        await page.keyboard.press("Enter")
        print("pergunta enviada; aguardando resposta do crew...")
        await page.wait_for_selector("text=Respondido em", timeout=120_000)
        await page.wait_for_timeout(900)
        expander = page.locator("summary:has-text('Detalhes da execução')").last
        await expander.scroll_into_view_if_needed()
        await expander.click()
        await page.wait_for_timeout(1_200)
        await page.mouse.wheel(0, 700)
        await page.wait_for_timeout(800)
        await capturar(
            page,
            "docs/assets/screenshot.png",
            ["TRIADOR", "REDATOR", "dossiê de evidências", "Detalhes da execução"],
        )

        # ── 2) Painel: metricas vivas do DuckDB ──
        await page.goto(f"{BASE}/?page=painel", wait_until="domcontentloaded")
        await page.wait_for_selector("text=Incidentes", timeout=60_000)
        await page.wait_for_timeout(1_500)
        await capturar(page, "docs/assets/screenshot-painel.png", ["Painel", "incidentes"])

        # ── 3) Observabilidade: diario de chamadas LLM (Etapa 2) ──
        await page.goto(f"{BASE}/?page=observabilidade", wait_until="domcontentloaded")
        await page.wait_for_selector("text=Diário de chamadas LLM", timeout=60_000)
        await page.wait_for_timeout(1_500)
        await capturar(
            page,
            "docs/assets/screenshot-observabilidade.png",
            ["Diário de chamadas LLM", "redator", "roteamento"],
        )

        await browser.close()
        print("todas as capturas concluidas")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FALHOU: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
