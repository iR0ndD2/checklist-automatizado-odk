"""Configuração lida de variáveis de ambiente (arquivo .env) e do formularios.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]  # raiz do repositório


def _env(nome: str, padrao: str | None = None, obrigatorio: bool = False) -> str:
    valor = os.environ.get(nome, padrao)
    if obrigatorio and not valor:
        raise RuntimeError(f"Variável de ambiente obrigatória não definida: {nome}")
    return valor or ""


@dataclass(frozen=True)
class Formulario:
    form_id: str
    xlsform: Path
    destinatarios: list[str]
    alerta: list[str] = field(default_factory=list)
    resultados_alerta: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    modo: str                    # "odk" (servidor real) ou "demo" (dados de exemplo)
    odk_url: str
    odk_email: str
    odk_senha: str
    odk_projeto_id: int
    banco_url: str
    smtp_host: str
    smtp_porta: int
    smtp_usuario: str
    smtp_senha: str
    smtp_tls: bool
    remetente: str
    intervalo_minutos: int
    pasta_saida: Path
    formularios: list[Formulario]

    @classmethod
    def carregar(cls, arquivo_formularios: Path | None = None) -> "Config":
        modo = _env("MODO", "demo").lower()
        if modo not in {"odk", "demo"}:
            raise RuntimeError("MODO deve ser 'odk' ou 'demo'")
        precisa_odk = modo == "odk"

        arquivo = arquivo_formularios or RAIZ / "integrador" / "formularios.toml"
        with open(arquivo, "rb") as f:
            dados = tomllib.load(f)
        formularios = [
            Formulario(
                form_id=item["form_id"],
                xlsform=RAIZ / item["xlsform"],
                destinatarios=item["destinatarios"],
                alerta=item.get("alerta", []),
                resultados_alerta=item.get("resultados_alerta", []),
            )
            for item in dados["formulario"]
        ]

        return cls(
            modo=modo,
            odk_url=_env("ODK_URL", obrigatorio=precisa_odk).rstrip("/"),
            odk_email=_env("ODK_EMAIL", obrigatorio=precisa_odk),
            odk_senha=_env("ODK_SENHA", obrigatorio=precisa_odk),
            odk_projeto_id=int(_env("ODK_PROJETO_ID", "1")),
            banco_url=_env("BANCO_URL", obrigatorio=True),
            smtp_host=_env("SMTP_HOST", "localhost"),
            smtp_porta=int(_env("SMTP_PORTA", "1025")),
            smtp_usuario=_env("SMTP_USUARIO"),
            smtp_senha=_env("SMTP_SENHA"),
            smtp_tls=_env("SMTP_TLS", "false").lower() == "true",
            remetente=_env("REMETENTE", "checklist@exemplo.com.br"),
            intervalo_minutos=int(_env("INTERVALO_MINUTOS", "5")),
            pasta_saida=Path(_env("PASTA_SAIDA", str(RAIZ / "saida"))),
            formularios=formularios,
        )
