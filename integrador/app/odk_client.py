"""Cliente da API do ODK Central.

Endpoints usados (documentação: https://docs.getodk.org/central-api/):
- POST /v1/sessions                                         login, devolve um token
- GET  /v1/projects/{p}/forms/{f}.svc/Submissions           respostas em OData (JSON)
- GET  /v1/projects/{p}/forms/{f}/submissions/{id}/attachments/{arquivo}   fotos e assinaturas
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Iterator, Protocol

import requests

log = logging.getLogger(__name__)

TAMANHO_PAGINA = 250


class FonteSubmissoes(Protocol):
    """O que o processador precisa de uma fonte de dados. O modo demo implementa o mesmo."""

    def submissoes(self, form_id: str, desde: datetime | None) -> Iterator[dict]: ...

    def anexo(self, form_id: str, instance_id: str, arquivo: str) -> bytes: ...


class ErroOdk(RuntimeError):
    pass


class OdkCentral:
    def __init__(self, url: str, email: str, senha: str, projeto_id: int,
                 tentativas: int = 3, timeout: int = 30):
        self.url = url.rstrip("/")
        self.email = email
        self._senha = senha
        self.projeto_id = projeto_id
        self.tentativas = tentativas
        self.timeout = timeout
        self._sessao = requests.Session()
        self._token: str | None = None

    # ------------------------------------------------------------------ autenticação

    def _autenticar(self) -> None:
        resposta = self._sessao.post(
            f"{self.url}/v1/sessions",
            json={"email": self.email, "password": self._senha},
            timeout=self.timeout,
        )
        if resposta.status_code != 200:
            raise ErroOdk(f"Falha no login do ODK Central (HTTP {resposta.status_code})")
        self._token = resposta.json()["token"]
        self._sessao.headers["Authorization"] = f"Bearer {self._token}"
        log.info("Sessão aberta no ODK Central")

    def _get(self, caminho: str, **kwargs) -> requests.Response:
        """GET com nova tentativa em falha de rede/5xx e novo login quando o token expira."""
        if not self._token:
            self._autenticar()
        espera = 2
        for tentativa in range(1, self.tentativas + 1):
            try:
                resposta = self._sessao.get(f"{self.url}{caminho}", timeout=self.timeout, **kwargs)
            except requests.RequestException as erro:
                if tentativa == self.tentativas:
                    raise ErroOdk(f"ODK Central inacessível: {erro}") from erro
                log.warning("Falha de rede (%s), tentativa %s de %s", erro, tentativa, self.tentativas)
            else:
                if resposta.status_code == 401 and tentativa < self.tentativas:
                    self._autenticar()
                    continue
                if resposta.status_code < 500:
                    if resposta.status_code >= 400:
                        raise ErroOdk(f"HTTP {resposta.status_code} em {caminho}: {resposta.text[:200]}")
                    return resposta
                if tentativa == self.tentativas:
                    raise ErroOdk(f"HTTP {resposta.status_code} em {caminho}")
                log.warning("HTTP %s, tentativa %s de %s", resposta.status_code, tentativa, self.tentativas)
            time.sleep(espera)
            espera *= 2
        raise ErroOdk("Número de tentativas esgotado")  # não deveria chegar aqui

    # ------------------------------------------------------------------ leitura

    def submissoes(self, form_id: str, desde: datetime | None) -> Iterator[dict]:
        """Respostas novas, da mais antiga para a mais recente, já com os grupos repetidos."""
        caminho = f"/v1/projects/{self.projeto_id}/forms/{form_id}.svc/Submissions"
        params = {
            "$expand": "*",
            "$orderby": "__system/submissionDate asc",
            "$top": TAMANHO_PAGINA,
        }
        if desde:
            params["$filter"] = f"__system/submissionDate gt {desde.isoformat()}"

        pular = 0
        while True:
            params["$skip"] = pular
            pagina = self._get(caminho, params=params).json().get("value", [])
            yield from pagina
            if len(pagina) < TAMANHO_PAGINA:
                return
            pular += TAMANHO_PAGINA

    def anexo(self, form_id: str, instance_id: str, arquivo: str) -> bytes:
        caminho = (f"/v1/projects/{self.projeto_id}/forms/{form_id}"
                   f"/submissions/{instance_id}/attachments/{arquivo}")
        return self._get(caminho).content
