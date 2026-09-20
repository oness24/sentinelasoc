"""Gera os ícones da aplicação (favicon minimalista) com Pillow.

Uso: ./venv/bin/python scripts/make_icons.py
Cria: assets/favicon.png (marca geométrica S sobre quadrado escuro)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DESTINO = Path(__file__).resolve().parent.parent / "assets"
DESTINO.mkdir(parents=True, exist_ok=True)

TAM = 512
BG = "#0a0e13"
PANEL = "#10161e"
BORDA = "#2dd4a7"
TEXTO = "#2dd4a7"

FONTES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]


def _fonte(tamanho: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for caminho in FONTES:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default()


def favicon() -> None:
    img = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # placa arredondada escura com borda teal
    raio = 96
    d.rounded_rectangle(
        [16, 16, TAM - 16, TAM - 16], radius=raio, fill=PANEL, outline=BORDA, width=8
    )

    # glifo S centralizado
    fonte = _fonte(300)
    caixa = d.textbbox((0, 0), "S", font=fonte)
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    d.text(((TAM - w) / 2 - caixa[0], (TAM - h) / 2 - caixa[1]), "S", font=fonte, fill=TEXTO)

    caminho = DESTINO / "favicon.png"
    img.save(caminho)
    print(f"OK {caminho}")


if __name__ == "__main__":
    favicon()
