"""Captura screenshots atualizados da UI (Copiloto com crew, Painel, Observabilidade).

Uso: ./venv/bin/python scripts/capture_screenshots.py
Requer: app rodando em http://localhost:8501 e Chrome instalado.

Alem de capturar, PROVA que os elementos-chave estao visiveis no viewport
(bounding box dentro da area da tela) — screenshot comprovado, nao cego.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

BASE = "http://localhost:8501"
PERGUNTA = "Qual o SLA de correção para uma CVE com CVSS 9.5 em ativo exposto?"
LARGURA, ALTURA = 1512, 1080


async def capturar(page, caminho: str, deve_conter: list[str]) -> None:
    """Screenshot + prova textual (DOM) + prova visual (chips no viewport)."""
    corpo = (await page.content()).lower()
    faltando = [t for t in deve_conter if t.lower() not in corpo]
    if faltando:
        raise AssertionError(f"{caminho}: nao achei na pagina: {faltando}")
    await page.screenshot(path=caminho, full_page=False)
    print(f"ok {caminho} (verificado: {', '.join(deve_conter)})")


async def visivel_no_viewport(page, seletor: str, nome: str) -> None:
    """Garante que o elemento existe, esta renderizado E dentro do viewport."""
    alvo = page.locator(seletor).first
    await alvo.wait_for(state="visible", timeout=30_000)
    caixa = await alvo.bounding_box()
    if not caixa:
        raise AssertionError(f"{nome}: sem bounding box")
    if caixa["y"] < 0 or caixa["y"] + caixa["height"] > ALTURA:
        fundo = caixa["y"] + caixa["height"]
        raise AssertionError(f"{nome}: fora do viewport (y={caixa['y']:.0f}, fundo={fundo:.0f})")
    print(f"visivel no viewport: {nome} (y={caixa['y']:.0f})")


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=2
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
        status = page.locator("text=Respondido em").first
        await status.wait_for(state="visible", timeout=120_000)
        await page.wait_for_timeout(900)
        # abre o rastro e rola o ULTIMO chip de agente para dentro da tela
        # (scroll minimo: status e resumo do expander ficam acima, visiveis)
        expander = page.locator("summary:has-text('Detalhes da execução')").last
        await expander.scroll_into_view_if_needed()
        await expander.click()
        await page.wait_for_timeout(1_200)
        ultimo_agente = page.locator(".tk-agente").last
        await ultimo_agente.scroll_into_view_if_needed()
        await page.wait_for_timeout(900)
        # prova visual: os tres elementos que o README promete estao NA IMAGEM
        await visivel_no_viewport(page, "text=Respondido em", "status 'Respondido em'")
        await visivel_no_viewport(
            page, "summary:has-text('Detalhes da execução')", "expander 'Detalhes da execução'"
        )
        await visivel_no_viewport(page, ".tk-agente", "chip TRIADOR/REDATOR")
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
        # garante a tabela por agente·etapa dentro da tela
        painel = page.locator("text=Por agente · etapa")
        await painel.scroll_into_view_if_needed()
        await page.wait_for_timeout(600)
        await visivel_no_viewport(page, ".tk-agente", "coluna agente (Observabilidade)")
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
    except Exception as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
