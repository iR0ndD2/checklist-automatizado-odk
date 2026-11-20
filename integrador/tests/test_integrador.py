"""Testes sem banco e sem servidor: usam a fonte demo e um repositório em memória."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.config import RAIZ, Config, Formulario
from app.demo import FonteDemo
from app.estrutura import carregar_estrutura
from app.processador import Processador
from app.regras import avaliar, buscar_campo
from app import relatorio

EXEMPLOS = RAIZ / "exemplos"
FORMS = ["vistoria_veiculo", "recebimento_doca", "manutencao_industrial"]


class RepositorioMemoria:
    """Mesmo contrato do Repositorio do PostgreSQL, guardado em dicionários."""

    def __init__(self):
        self.submissoes: dict[str, dict] = {}
        self.controle: dict[str, datetime] = {}
        self.emails: list[tuple] = []

    def ultima_data(self, form_id):
        return self.controle.get(form_id)

    def salvar_submissao(self, form_id, resposta, resultado, qtd, alerta):
        data = datetime.fromisoformat(resposta["__system"]["submissionDate"])
        self.controle[form_id] = max(self.controle.get(form_id, data), data)
        if resposta["__id"] in self.submissoes:
            return False
        self.submissoes[resposta["__id"]] = {
            "instance_id": resposta["__id"], "form_id": form_id, "enviado_em": data,
            "resultado": resultado, "qtd_nao_conformes": qtd, "alerta": alerta,
            "dados": resposta, "status": "pendente", "tentativas": 0,
        }
        return True

    def pendentes(self, form_id):
        return [s for s in self.submissoes.values()
                if s["form_id"] == form_id and s["status"] in ("pendente", "erro")]

    def marcar_enviado(self, instance_id, arquivo_pdf, destinatarios, assunto):
        self.submissoes[instance_id].update(status="enviado", arquivo_pdf=arquivo_pdf)
        self.emails.append((instance_id, destinatarios, assunto))

    def marcar_erro(self, instance_id, erro):
        s = self.submissoes[instance_id]
        s.update(status="erro", ultimo_erro=erro, tentativas=s["tentativas"] + 1)


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("MODO", "demo")
    monkeypatch.setenv("BANCO_URL", "postgresql://nao-usado")
    monkeypatch.setenv("PASTA_SAIDA", str(tmp_path))
    return Config.carregar()


def form(config, form_id) -> Formulario:
    return next(f for f in config.formularios if f.form_id == form_id)


@pytest.mark.parametrize("form_id", FORMS)
def test_estrutura_le_rotulos_do_xlsform(config, form_id):
    estrutura = carregar_estrutura(form(config, form_id).xlsform)
    assert estrutura.form_id == form_id
    assert estrutura.titulo
    nomes = {c.nome for s in estrutura.secoes for c in s.campos}
    assert "inicio" not in nomes            # metadado técnico não vai para o PDF
    assert "qtd_nao_conformes" not in nomes  # cálculo interno também não


def test_rotulo_de_opcao_multipla(config):
    estrutura = carregar_estrutura(form(config, "manutencao_industrial").xlsform)
    campo = next(c for s in estrutura.secoes for c in s.campos if c.nome == "epi")
    assert estrutura.rotulo_opcao(campo, "oculos botina") == "Óculos, Botina"


def test_buscar_campo_em_grupo_aninhado():
    assert buscar_campo({"a": {"b": {"resultado": "ok"}}}, "resultado") == "ok"
    assert buscar_campo({"__system": {"resultado": "x"}}, "resultado") is None


@pytest.mark.parametrize("form_id,resultado,alerta", [
    ("vistoria_veiculo", "com_avarias", True),
    ("recebimento_doca", "aprovado_ressalva", True),
    ("manutencao_industrial", "liberado_restricao", True),
])
def test_regras_dos_exemplos(config, form_id, resultado, alerta):
    resposta = next(FonteDemo(EXEMPLOS).submissoes(form_id, None))
    obtido, qtd, precisa_alerta = avaliar(form(config, form_id), resposta)
    assert obtido == resultado
    assert qtd >= 1
    assert precisa_alerta is alerta


def test_sem_nao_conformidade_e_resultado_bom_nao_alerta(config):
    resposta = {"encerramento": {"resultado": "aprovado", "qtd_nao_conformes": "0"}}
    assert avaliar(form(config, "vistoria_veiculo"), resposta) == ("aprovado", 0, False)


def test_html_tem_fotos_tabela_e_destaque(config):
    f = form(config, "recebimento_doca")
    estrutura = carregar_estrutura(f.xlsform)
    fonte = FonteDemo(EXEMPLOS)
    resposta = next(fonte.submissoes(f.form_id, None))
    anexos = {a: fonte.anexo(f.form_id, resposta["__id"], a)
              for a in relatorio.arquivos_de_imagem(estrutura, resposta)}
    html = relatorio.gerar_html(estrutura, resposta, anexos, "aprovado_ressalva", 1, True)
    assert "Aprovado com ressalva" in html
    assert "104523" in html                        # nota fiscal do grupo repetido
    assert html.count("data:image/") == len(anexos) == 3
    assert 'class="nc"' in html


def test_ciclo_completo_envia_um_email_por_resposta_e_nao_repete(config):
    repo = RepositorioMemoria()
    enviados = []
    processador = Processador(config, FonteDemo(EXEMPLOS), repo,
                              enviar_email=lambda cfg, dest, assunto, corpo, pdf: enviados.append((dest, assunto, pdf)))

    resumo = processador.executar()
    assert (resumo.novas, resumo.enviadas, resumo.erros) == (3, 3, 0)
    assert all(Path(pdf).exists() and Path(pdf).stat().st_size > 10_000 for _, _, pdf in enviados)
    assert all(assunto.startswith("[ATENÇÃO]") for _, assunto, _ in enviados)
    destinos_doca = next(d for d, a, _ in enviados if "recebimento" in a.lower())
    assert "qualidade@exemplo.com.br" in destinos_doca

    segundo = processador.executar()             # mesma fonte, nada de novo
    assert (segundo.novas, segundo.enviadas) == (0, 0)
    assert len(enviados) == 3


def test_falha_no_email_fica_registrada_para_nova_tentativa(config):
    repo = RepositorioMemoria()

    def smtp_fora(*_):
        raise ConnectionRefusedError("SMTP indisponível")

    resumo = Processador(config, FonteDemo(EXEMPLOS), repo, enviar_email=smtp_fora).executar()
    assert resumo.erros == 3
    assert all(s["status"] == "erro" and "SMTP" in s["ultimo_erro"] for s in repo.submissoes.values())

    # o SMTP volta: o próximo ciclo reenvia o que ficou para trás
    resumo = Processador(config, FonteDemo(EXEMPLOS), repo, enviar_email=lambda *a: None).executar()
    assert resumo.enviadas == 3
