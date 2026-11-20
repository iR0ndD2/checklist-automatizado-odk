"""Fonte de dados de demonstração: lê respostas de exemplo do disco.

Permite rodar o projeto inteiro (banco, PDF e e-mail) sem um servidor ODK Central,
com o mesmo formato JSON que a API OData devolve.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator


class FonteDemo:
    def __init__(self, pasta: Path):
        self.pasta = pasta  # exemplos/submissoes/<form_id>/*.json e exemplos/midia/

    def submissoes(self, form_id: str, desde: datetime | None) -> Iterator[dict]:
        respostas = []
        for arquivo in sorted((self.pasta / "submissoes" / form_id).glob("*.json")):
            resposta = json.loads(arquivo.read_text(encoding="utf-8"))
            data = datetime.fromisoformat(resposta["__system"]["submissionDate"])
            if desde is None or data > desde:
                respostas.append((data, resposta))
        for _, resposta in sorted(respostas, key=lambda par: par[0]):
            yield resposta

    def anexo(self, form_id: str, instance_id: str, arquivo: str) -> bytes:
        return (self.pasta / "midia" / arquivo).read_bytes()
