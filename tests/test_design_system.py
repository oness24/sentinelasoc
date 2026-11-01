"""Invariantes da paleta: um token declarado duas vezes vence em silencio e
vaza a cor errada para todo lugar que o usa (foi o que apagou o painel de
rastro atras de um lilas claro)."""

import collections
import re
import tomllib
from pathlib import Path

from sentinelasoc.web.shell import CSS

RAIZ = Path(__file__).resolve().parents[1]
TOKENS = re.search(r":root \{(.*?)\n\}", CSS, re.S).group(1)
DECLARADOS = re.findall(r"(--[\w-]+)\s*:", TOKENS)
USADOS = set(re.findall(r"var\((--[\w-]+)\)", CSS))


def test_nenhum_token_declarado_duas_vezes():
    repetidos = [n for n, c in collections.Counter(DECLARADOS).items() if c > 1]
    assert not repetidos, f"tokens duplicados em :root: {repetidos}"


def test_todo_token_usado_existe():
    assert not USADOS - set(DECLARADOS)


def test_nenhum_token_morto():
    assert not set(DECLARADOS) - USADOS - {"--mono", "--ui"}


def test_tema_nativo_espelha_os_tokens():
    """Streamlit pinta foco, spinner e cabecalho de status com o tema do
    config.toml; divergir dos tokens exibe duas paletas ao mesmo tempo."""
    tema = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text())["theme"]
    cor = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", TOKENS))
    assert tema["primaryColor"] == cor["--ouro"]
    assert tema["backgroundColor"] == cor["--canvas"]
    assert tema["secondaryBackgroundColor"] == cor["--painel"]
    assert tema["textColor"] == cor["--text"]
