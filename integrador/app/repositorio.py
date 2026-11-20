"""Acesso ao PostgreSQL."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
MAX_TENTATIVAS = 5


class Repositorio:
    def __init__(self, url: str):
        self.conexao = psycopg.connect(url, row_factory=dict_row, autocommit=True)

    def criar_estrutura(self) -> None:
        self.conexao.execute(SCHEMA.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ carga incremental

    def ultima_data(self, form_id: str) -> datetime | None:
        linha = self.conexao.execute(
            "SELECT ultima_data FROM controle_carga WHERE form_id = %s", (form_id,)
        ).fetchone()
        return linha["ultima_data"] if linha else None

    def salvar_submissao(self, form_id: str, resposta: dict, resultado: str | None,
                         qtd_nao_conformes: int, alerta: bool) -> bool:
        """Grava a resposta e avança o controle de carga na mesma transação.

        Devolve False se a resposta já existia (a mesma resposta lida duas vezes não
        gera dois e-mails).
        """
        sistema = resposta["__system"]
        with self.conexao.transaction():
            inserida = self.conexao.execute(
                """
                INSERT INTO submissao (instance_id, form_id, enviado_em, enviado_por,
                                       resultado, qtd_nao_conformes, alerta, dados)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (instance_id) DO NOTHING
                """,
                (resposta["__id"], form_id, sistema["submissionDate"], sistema.get("submitterName"),
                 resultado, qtd_nao_conformes, alerta, Jsonb(resposta)),
            ).rowcount == 1
            self.conexao.execute(
                """
                INSERT INTO controle_carga (form_id, ultima_data) VALUES (%s, %s)
                ON CONFLICT (form_id) DO UPDATE
                    SET ultima_data = GREATEST(controle_carga.ultima_data, EXCLUDED.ultima_data),
                        atualizado_em = now()
                """,
                (form_id, sistema["submissionDate"]),
            )
        return inserida

    # ------------------------------------------------------------------ fila de envio

    def pendentes(self, form_id: str) -> list[dict]:
        return self.conexao.execute(
            """
            SELECT * FROM submissao
            WHERE form_id = %s AND status IN ('pendente', 'erro') AND tentativas < %s
            ORDER BY enviado_em
            """,
            (form_id, MAX_TENTATIVAS),
        ).fetchall()

    def marcar_enviado(self, instance_id: str, arquivo_pdf: str, destinatarios: list[str],
                       assunto: str) -> None:
        with self.conexao.transaction():
            self.conexao.execute(
                """
                UPDATE submissao
                SET status = 'enviado', arquivo_pdf = %s, processado_em = now(),
                    tentativas = tentativas + 1, ultimo_erro = NULL
                WHERE instance_id = %s
                """,
                (arquivo_pdf, instance_id),
            )
            self.conexao.execute(
                "INSERT INTO envio_email (instance_id, destinatarios, assunto) VALUES (%s, %s, %s)",
                (instance_id, destinatarios, assunto),
            )

    def marcar_erro(self, instance_id: str, erro: str) -> None:
        self.conexao.execute(
            """
            UPDATE submissao
            SET status = 'erro', tentativas = tentativas + 1, ultimo_erro = %s
            WHERE instance_id = %s
            """,
            (erro[:1000], instance_id),
        )
