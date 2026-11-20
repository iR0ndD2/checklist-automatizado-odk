"""Ponto de entrada.

    python -m app executar   # um ciclo e termina (bom para testar ou rodar via cron)
    python -m app agendar    # fica rodando e repete a cada INTERVALO_MINUTOS
"""

from __future__ import annotations

import argparse
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import RAIZ, Config
from .demo import FonteDemo
from .odk_client import OdkCentral
from .processador import Processador
from .repositorio import Repositorio


def montar() -> tuple[Config, Processador]:
    config = Config.carregar()
    if config.modo == "demo":
        fonte = FonteDemo(RAIZ / "exemplos")
        logging.info("Modo demonstração: lendo respostas de exemplos/")
    else:
        fonte = OdkCentral(config.odk_url, config.odk_email, config.odk_senha, config.odk_projeto_id)
    repo = Repositorio(config.banco_url)
    repo.criar_estrutura()
    return config, Processador(config, fonte, repo)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("fontTools").setLevel(logging.WARNING)  # o WeasyPrint é verboso
    parser = argparse.ArgumentParser(prog="python -m app")
    parser.add_argument("comando", choices=["executar", "agendar"])
    args = parser.parse_args()

    config, processador = montar()

    if args.comando == "executar":
        resumo = processador.executar()
        return 1 if resumo.erros else 0

    agenda = BlockingScheduler(timezone="America/Sao_Paulo")
    # max_instances=1: se um ciclo demorar, o próximo espera em vez de rodar em paralelo
    agenda.add_job(processador.executar, "interval", minutes=config.intervalo_minutos,
                   max_instances=1, coalesce=True, next_run_time=None)
    processador.executar()
    logging.info("Agendado a cada %s minuto(s). Ctrl+C para parar.", config.intervalo_minutos)
    try:
        agenda.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
