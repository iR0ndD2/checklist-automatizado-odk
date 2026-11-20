"""Orquestra um ciclo: buscar respostas novas, gravar, gerar PDF e enviar."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from html import escape
from pathlib import Path

from . import email_envio, relatorio
from .config import Config, Formulario
from .estrutura import Estrutura, carregar_estrutura
from .odk_client import FonteSubmissoes
from .regras import avaliar

log = logging.getLogger(__name__)


@dataclass
class Resumo:
    novas: int = 0
    enviadas: int = 0
    erros: int = 0


def _nome_arquivo(texto: str) -> str:
    """Nome de arquivo seguro: sem acentos, espaços ou símbolos."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_-]+", "_", texto).strip("_")[:80]


class Processador:
    def __init__(self, config: Config, fonte: FonteSubmissoes, repositorio, enviar_email=None):
        self.config = config
        self.fonte = fonte
        self.repo = repositorio
        self.enviar_email = enviar_email or email_envio.enviar
        self._estruturas: dict[str, Estrutura] = {}

    def estrutura(self, formulario: Formulario) -> Estrutura:
        if formulario.form_id not in self._estruturas:
            self._estruturas[formulario.form_id] = carregar_estrutura(formulario.xlsform)
        return self._estruturas[formulario.form_id]

    def executar(self) -> Resumo:
        resumo = Resumo()
        for formulario in self.config.formularios:
            try:
                resumo.novas += self._carregar(formulario)
            except Exception:
                log.exception("Falha ao buscar respostas de %s", formulario.form_id)
                resumo.erros += 1
                continue  # um formulário com problema não para os outros
            enviadas, erros = self._enviar_pendentes(formulario)
            resumo.enviadas += enviadas
            resumo.erros += erros
        log.info("Ciclo concluído: %s novas, %s enviadas, %s erros",
                 resumo.novas, resumo.enviadas, resumo.erros)
        return resumo

    # ------------------------------------------------------------------ etapa 1: carga

    def _carregar(self, formulario: Formulario) -> int:
        desde = self.repo.ultima_data(formulario.form_id)
        novas = 0
        for resposta in self.fonte.submissoes(formulario.form_id, desde):
            resultado, qtd, alerta = avaliar(formulario, resposta)
            if self.repo.salvar_submissao(formulario.form_id, resposta, resultado, qtd, alerta):
                novas += 1
        if novas:
            log.info("%s: %s resposta(s) nova(s)", formulario.form_id, novas)
        return novas

    # ------------------------------------------------------------------ etapa 2: PDF + e-mail

    def _enviar_pendentes(self, formulario: Formulario) -> tuple[int, int]:
        enviadas = erros = 0
        for item in self.repo.pendentes(formulario.form_id):
            try:
                self._processar(formulario, item)
                enviadas += 1
            except Exception as erro:
                log.exception("Falha ao processar %s", item["instance_id"])
                self.repo.marcar_erro(item["instance_id"], f"{type(erro).__name__}: {erro}")
                erros += 1
        return enviadas, erros

    def _processar(self, formulario: Formulario, item: dict) -> None:
        estrutura = self.estrutura(formulario)
        resposta = item["dados"]
        instance_id = item["instance_id"]

        anexos = {
            arquivo: self.fonte.anexo(formulario.form_id, instance_id, arquivo)
            for arquivo in relatorio.arquivos_de_imagem(estrutura, resposta)
        }
        html = relatorio.gerar_html(estrutura, resposta, anexos, item["resultado"],
                                    item["qtd_nao_conformes"], item["alerta"])

        identificacao = resposta.get("meta", {}).get("instanceName") or instance_id
        data = item["enviado_em"].strftime("%Y-%m-%d") if hasattr(item["enviado_em"], "strftime") \
            else str(item["enviado_em"])[:10]
        destino = (self.config.pasta_saida / formulario.form_id / data /
                   f"{_nome_arquivo(identificacao)}_{_nome_arquivo(instance_id)[-8:]}.pdf")
        relatorio.gerar_pdf(html, destino)

        destinatarios = list(formulario.destinatarios)
        prefixo = ""
        if item["alerta"]:
            destinatarios += [d for d in formulario.alerta if d not in destinatarios]
            prefixo = "[ATENÇÃO] "
        resultado = relatorio.resultado_legivel(estrutura, item["resultado"])
        assunto = f"{prefixo}{estrutura.titulo}: {identificacao}"
        corpo = email_envio.corpo(escape(estrutura.titulo), escape(identificacao), escape(resultado),
                                  item["qtd_nao_conformes"], item["alerta"])

        self.enviar_email(self.config, destinatarios, assunto, corpo, destino)
        self.repo.marcar_enviado(instance_id, str(destino), destinatarios, assunto)
        log.info("Enviado: %s -> %s", assunto, ", ".join(destinatarios))
