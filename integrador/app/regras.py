"""Regras de negócio: resultado da inspeção e quando disparar alerta."""

from __future__ import annotations

from .config import Formulario


def buscar_campo(dados, nome: str):
    """Procura um campo em qualquer nível de grupo da resposta do ODK."""
    if isinstance(dados, dict):
        if nome in dados:
            return dados[nome]
        for chave, valor in dados.items():
            if chave.startswith("__"):
                continue
            achado = buscar_campo(valor, nome)
            if achado is not None:
                return achado
    return None


def avaliar(formulario: Formulario, resposta: dict) -> tuple[str | None, int, bool]:
    """Devolve (resultado, quantidade de não conformidades, precisa de alerta)."""
    resultado = buscar_campo(resposta, "resultado")
    try:
        qtd = int(float(buscar_campo(resposta, "qtd_nao_conformes") or 0))
    except (TypeError, ValueError):
        qtd = 0
    alerta = qtd > 0 or (resultado in formulario.resultados_alerta)
    return resultado, qtd, alerta
