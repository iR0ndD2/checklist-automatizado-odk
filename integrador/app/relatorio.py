"""Monta o relatório da inspeção em PDF."""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .estrutura import Campo, Estrutura, Secao

TEMPLATES = Path(__file__).resolve().parent / "templates"
FUSO = ZoneInfo("America/Sao_Paulo")

_jinja = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


@dataclass
class Linha:
    rotulo: str
    valor: str = ""
    imagem: str = ""          # data URI, quando o campo é foto ou assinatura
    assinatura: bool = False
    nao_conforme: bool = False


@dataclass
class SecaoRelatorio:
    rotulo: str
    linhas: list[Linha] = field(default_factory=list)
    tabela: list[list[str]] | None = None     # grupos repetidos (ex.: notas fiscais)
    colunas: list[str] = field(default_factory=list)


def _buscar(dados: dict, caminho: tuple[str, ...]):
    for chave in caminho:
        if not isinstance(dados, dict):
            return None
        dados = dados.get(chave)
    return dados


def _data_uri(conteudo: bytes, arquivo: str) -> str:
    tipo = mimetypes.guess_type(arquivo)[0] or "image/jpeg"
    return f"data:{tipo};base64,{base64.b64encode(conteudo).decode()}"


def _formatar(estrutura: Estrutura, campo: Campo, valor) -> str:
    if valor in (None, ""):
        return ""
    if campo.tipo == "geopoint" and isinstance(valor, dict):
        lon, lat, *_ = valor.get("coordinates", [None, None])
        precisao = (valor.get("properties") or {}).get("accuracy")
        texto = f"{lat:.6f}, {lon:.6f}"
        return f"{texto} (precisão {precisao:.0f} m)" if precisao else texto
    if campo.tipo in ("select_one", "select_multiple"):
        return estrutura.rotulo_opcao(campo, valor)
    if campo.tipo == "decimal":
        return f"{float(valor):.1f}".replace(".", ",")
    return str(valor)


def montar_secoes(estrutura: Estrutura, resposta: dict, anexos: dict[str, bytes]) -> list[SecaoRelatorio]:
    secoes = []
    for secao in estrutura.secoes:
        if secao.repetir:
            secoes.append(_secao_repetida(estrutura, secao, resposta))
            continue

        grupo = _buscar(resposta, secao.caminho) if secao.caminho else resposta
        if not isinstance(grupo, dict):
            continue  # grupo não exibido no formulário (relevância falsa)
        rel = SecaoRelatorio(secao.rotulo)
        for campo in secao.campos:
            valor = grupo.get(campo.nome)
            if valor in (None, ""):
                continue  # pergunta não exibida ou não respondida
            if campo.tipo == "image":
                if valor in anexos:
                    rel.linhas.append(Linha(campo.rotulo, imagem=_data_uri(anexos[valor], valor),
                                            assinatura=campo.assinatura))
                continue
            rel.linhas.append(Linha(campo.rotulo, _formatar(estrutura, campo, valor),
                                    nao_conforme=valor == "nao_conforme"))
        if rel.linhas:
            secoes.append(rel)
    return secoes


def _secao_repetida(estrutura: Estrutura, secao: Secao, resposta: dict) -> SecaoRelatorio:
    itens = _buscar(resposta, secao.caminho) or []
    linhas = [[_formatar(estrutura, c, item.get(c.nome)) for c in secao.campos] for item in itens]
    return SecaoRelatorio(secao.rotulo, tabela=linhas, colunas=[c.rotulo for c in secao.campos])


def arquivos_de_imagem(estrutura: Estrutura, resposta: dict) -> list[str]:
    """Nomes dos arquivos de foto e assinatura que a resposta referencia."""
    nomes = []
    for secao in estrutura.secoes:
        if secao.repetir:
            continue
        grupo = _buscar(resposta, secao.caminho) if secao.caminho else resposta
        if isinstance(grupo, dict):
            nomes += [grupo[c.nome] for c in secao.campos if c.tipo == "image" and grupo.get(c.nome)]
    return nomes


def gerar_html(estrutura: Estrutura, resposta: dict, anexos: dict[str, bytes],
               resultado: str | None, qtd_nao_conformes: int, alerta: bool) -> str:
    sistema = resposta["__system"]
    enviado = datetime.fromisoformat(sistema["submissionDate"].replace("Z", "+00:00")).astimezone(FUSO)
    return _jinja.get_template("relatorio.html").render(
        titulo=estrutura.titulo,
        identificacao=resposta.get("meta", {}).get("instanceName") or resposta["__id"],
        instance_id=resposta["__id"],
        enviado_em=enviado.strftime("%d/%m/%Y %H:%M"),
        enviado_por=sistema.get("submitterName") or "-",
        resultado=resultado_legivel(estrutura, resultado),
        qtd_nao_conformes=qtd_nao_conformes,
        alerta=alerta,
        secoes=montar_secoes(estrutura, resposta, anexos),
        gerado_em=datetime.now(FUSO).strftime("%d/%m/%Y %H:%M"),
    )


def resultado_legivel(estrutura: Estrutura, resultado: str | None) -> str:
    if not resultado:
        return "-"
    for opcoes in estrutura.opcoes.values():
        if resultado in opcoes:
            return opcoes[resultado]
    return resultado.replace("_", " ").capitalize()


def gerar_pdf(html: str, destino: Path) -> Path:
    from weasyprint import HTML  # importação tardia: só quem gera PDF precisa das libs do sistema

    destino.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(TEMPLATES)).write_pdf(destino)
    return destino
