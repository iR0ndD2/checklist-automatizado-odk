"""Lê a estrutura do formulário direto do XLSForm.

O próprio .xlsx publicado no ODK Central é a fonte dos rótulos do PDF. Se alguém muda
uma pergunta no formulário, o relatório acompanha sem mexer em código.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

# Tipos que não aparecem no relatório (metadados técnicos e textos de instrução)
TIPOS_OCULTOS = {"start", "end", "deviceid", "today", "username", "note", "calculate"}


@dataclass
class Campo:
    nome: str
    tipo: str            # ex.: "text", "select_one", "image"
    rotulo: str
    lista: str = ""      # lista de opções (select_one / select_multiple)
    aparencia: str = ""

    @property
    def assinatura(self) -> bool:
        return self.tipo == "image" and "signature" in self.aparencia


@dataclass
class Secao:
    nome: str
    rotulo: str
    repetir: bool = False                       # True para begin_repeat (vira tabela)
    campos: list[Campo] = field(default_factory=list)
    caminho: tuple[str, ...] = ()               # chaves aninhadas no JSON do ODK


@dataclass
class Estrutura:
    titulo: str
    form_id: str
    secoes: list[Secao]
    opcoes: dict[str, dict[str, str]]           # lista -> {valor: rótulo}

    def rotulo_opcao(self, campo: Campo, valor) -> str:
        if valor in (None, ""):
            return ""
        if campo.tipo == "select_multiple":
            return ", ".join(self.opcoes.get(campo.lista, {}).get(v, v) for v in str(valor).split())
        if campo.lista:
            return self.opcoes.get(campo.lista, {}).get(str(valor), str(valor))
        return str(valor)


def _linhas(ws) -> list[dict]:
    linhas = list(ws.iter_rows(values_only=True))
    cabecalho = [str(c).strip() if c else "" for c in linhas[0]]
    return [
        {cabecalho[i]: ("" if v is None else str(v)) for i, v in enumerate(linha) if i < len(cabecalho)}
        for linha in linhas[1:]
        if any(v not in (None, "") for v in linha)
    ]


def carregar_estrutura(xlsform: Path) -> Estrutura:
    wb = load_workbook(xlsform, read_only=True, data_only=True)
    survey = _linhas(wb["survey"])
    choices = _linhas(wb["choices"])
    settings = _linhas(wb["settings"])[0]

    opcoes: dict[str, dict[str, str]] = {}
    for c in choices:
        opcoes.setdefault(c["list_name"], {})[c["name"]] = c["label"]

    secoes: list[Secao] = [Secao("geral", "Dados gerais")]
    pilha: list[Secao] = []      # grupos abertos
    caminho: list[str] = []

    for linha in survey:
        tipo_completo = linha.get("type", "").strip()
        tipo, _, lista = tipo_completo.partition(" ")
        nome = linha.get("name", "")

        if tipo in ("begin_group", "begin_repeat"):
            caminho.append(nome)
            secao = Secao(nome, linha.get("label") or nome, repetir=tipo == "begin_repeat",
                          caminho=tuple(caminho))
            pilha.append(secao)
            secoes.append(secao)
            continue
        if tipo in ("end_group", "end_repeat"):
            pilha.pop()
            caminho.pop()
            continue
        if tipo in TIPOS_OCULTOS:
            continue

        campo = Campo(nome=nome, tipo=tipo, rotulo=linha.get("label") or nome,
                      lista=lista, aparencia=linha.get("appearance", ""))
        (pilha[-1] if pilha else secoes[0]).campos.append(campo)

    return Estrutura(
        titulo=settings.get("form_title", ""),
        form_id=settings.get("form_id", ""),
        secoes=[s for s in secoes if s.campos],
        opcoes=opcoes,
    )
