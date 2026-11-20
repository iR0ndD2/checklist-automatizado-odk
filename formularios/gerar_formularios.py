"""Gera os formulários XLSForm (.xlsx) do projeto a partir de definições em Python.

Por que gerar em vez de editar o .xlsx à mão?
- O .xlsx é binário: no GitHub não dá para ver o que mudou de uma versão para outra.
- Aqui cada formulário é texto, revisável em pull request, e o .xlsx é só o artefato final.

Uso:
    python formularios/gerar_formularios.py          # gera os três .xlsx em formularios/
    python formularios/gerar_formularios.py --validar  # gera e valida com o pyxform
"""

from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

PASTA = Path(__file__).resolve().parent

COLUNAS_SURVEY = [
    "type", "name", "label", "hint", "required", "relevant",
    "constraint", "constraint_message", "appearance", "calculation", "default", "parameters",
]

# Fotos reduzidas no próprio celular: envio mais rápido no 4G e menos espaço no servidor
PARAMETRO_FOTO = "max-pixels=1280"
COLUNAS_CHOICES = ["list_name", "name", "label"]
COLUNAS_SETTINGS = ["form_title", "form_id", "version", "instance_name", "default_language"]

# Placa no padrão antigo (ABC1234) ou Mercosul (ABC1D23)
REGEX_PLACA = "regex(., '^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$')"


def q(type_: str, name: str, label: str = "", **extra) -> dict:
    """Uma linha da aba survey."""
    if type_ == "image" and extra.get("appearance") != "signature":
        extra.setdefault("parameters", PARAMETRO_FOTO)
    return {"type": type_, "name": name, "label": label, **extra}


def metadados() -> list[dict]:
    """Campos que o ODK preenche sozinho: início, fim e aparelho."""
    return [q("start", "inicio"), q("end", "fim"), q("deviceid", "aparelho")]


def item_checklist(nome: str, rotulo: str, dica: str = "") -> list[dict]:
    """Item conforme / não conforme / não se aplica.

    Quando o item é marcado como não conforme, foto e descrição passam a ser obrigatórias.
    É isso que faz o checklist digital valer mais que o papel: a evidência vem junto.
    """
    nao_conforme = f"${{{nome}}} = 'nao_conforme'"
    return [
        q("select_one conformidade", nome, rotulo, hint=dica, required="yes",
          appearance="horizontal-compact"),
        q("image", f"{nome}_foto", f"Foto: {rotulo.lower()}", required="yes",
          relevant=nao_conforme, appearance="new"),
        q("text", f"{nome}_obs", "Descreva o problema", required="yes",
          relevant=nao_conforme, appearance="multiline"),
    ]


def grupo(nome: str, rotulo: str, linhas: list[dict], relevant: str = "") -> list[dict]:
    abre = q("begin_group", nome, rotulo, appearance="field-list")
    if relevant:
        abre["relevant"] = relevant
    return [abre, *linhas, q("end_group", nome)]


def contar_nao_conformes(nomes: list[str]) -> str:
    """Expressão XPath que soma quantos itens foram marcados como não conformes."""
    return " + ".join(f"if(${{{n}}} = 'nao_conforme', 1, 0)" for n in nomes)


ESCOLHAS_CONFORMIDADE = [
    ("conformidade", "conforme", "Conforme"),
    ("conformidade", "nao_conforme", "Não conforme"),
    ("conformidade", "na", "Não se aplica"),
]


# --------------------------------------------------------------------------------------
# 1. Vistoria de veículos — locadoras e empresas com frota própria
# --------------------------------------------------------------------------------------

def vistoria_veiculo() -> dict:
    itens_externos = [
        ("lataria", "Lataria e pintura", "Amassados, riscos, ferrugem"),
        ("vidros", "Para-brisa e vidros", "Trincas ou lascas"),
        ("farois", "Faróis, lanternas e setas", "Teste todos acesos"),
        ("pneus", "Pneus e estepe", "Calibragem, desgaste, bolhas"),
        ("retrovisores", "Retrovisores", ""),
    ]
    itens_internos = [
        ("bancos", "Bancos e forração", "Rasgos, manchas"),
        ("painel_luzes", "Luzes de alerta no painel", "Alguma luz de falha acesa?"),
        ("ar_condicionado", "Ar-condicionado", ""),
        ("equipamentos", "Triângulo, macaco e chave de roda", ""),
        ("documento", "Documento do veículo (CRLV)", "Físico ou digital"),
    ]
    todos = [n for n, _, _ in itens_externos + itens_internos]

    survey = [
        *metadados(),
        q("note", "intro", "**Vistoria de veículo**\n\nRegistre o estado do veículo na retirada, "
          "na devolução ou em uma vistoria de rotina. Itens não conformes exigem foto."),
        *grupo("identificacao", "Identificação", [
            q("select_one tipo_vistoria", "tipo_vistoria", "Tipo de vistoria", required="yes"),
            q("text", "placa", "Placa", hint="Somente letras maiúsculas e números, ex.: ABC1D23",
              required="yes", constraint=REGEX_PLACA,
              constraint_message="Placa inválida. Use o padrão ABC1234 ou ABC1D23."),
            q("text", "modelo", "Modelo do veículo", required="yes"),
            q("integer", "km", "Quilometragem (km)", required="yes",
              constraint=". >= 0 and . <= 2000000", constraint_message="Valor fora do esperado."),
            q("select_one combustivel", "combustivel", "Nível de combustível", required="yes",
              appearance="horizontal-compact"),
            q("text", "condutor", "Nome do condutor", required="yes"),
            q("text", "contrato", "Nº do contrato ou da reserva",
              hint="Locadora: número do contrato. Frota própria: centro de custo ou ordem."),
        ]),
        *grupo("fotos", "Fotos obrigatórias", [
            q("image", "foto_frente", "Frente", required="yes", appearance="new"),
            q("image", "foto_traseira", "Traseira", required="yes", appearance="new"),
            q("image", "foto_lateral_esq", "Lateral esquerda", required="yes", appearance="new"),
            q("image", "foto_lateral_dir", "Lateral direita", required="yes", appearance="new"),
            q("image", "foto_painel", "Painel com a quilometragem", required="yes", appearance="new"),
        ]),
        *grupo("externo", "Itens externos",
               [linha for n, r, d in itens_externos for linha in item_checklist(n, r, d)]),
        *grupo("interno", "Itens internos e documentos",
               [linha for n, r, d in itens_internos for linha in item_checklist(n, r, d)]),
        *grupo("encerramento", "Encerramento", [
            q("calculate", "qtd_nao_conformes", calculation=contar_nao_conformes(todos)),
            q("calculate", "resultado",
              calculation="if(${qtd_nao_conformes} = 0, 'aprovado', 'com_avarias')"),
            q("note", "resumo", "Itens não conformes: **${qtd_nao_conformes}**"),
            q("text", "observacoes", "Observações gerais", appearance="multiline"),
            q("geopoint", "local", "Local da vistoria", hint="Aguarde a precisão estabilizar"),
            q("text", "vistoriador", "Nome de quem fez a vistoria", required="yes"),
            q("image", "assinatura_condutor", "Assinatura do condutor", required="yes",
              appearance="signature"),
        ]),
    ]
    choices = [
        *ESCOLHAS_CONFORMIDADE,
        ("tipo_vistoria", "retirada", "Retirada"),
        ("tipo_vistoria", "devolucao", "Devolução"),
        ("tipo_vistoria", "rotina", "Rotina / preventiva"),
        ("combustivel", "reserva", "Reserva"),
        ("combustivel", "um_quarto", "1/4"),
        ("combustivel", "meio", "1/2"),
        ("combustivel", "tres_quartos", "3/4"),
        ("combustivel", "cheio", "Cheio"),
    ]
    settings = {
        "form_title": "Vistoria de veículo",
        "form_id": "vistoria_veiculo",
        "version": "2026112001",
        "instance_name": "concat(${placa}, ' - ', jr:choice-name(${tipo_vistoria}, '${tipo_vistoria}'), ' - ', format-date(today(), '%d/%m/%Y'))",
        "default_language": "pt",
    }
    return {"arquivo": "vistoria_veiculo.xlsx", "survey": survey, "choices": choices,
            "settings": settings}


# --------------------------------------------------------------------------------------
# 2. Inspeção de recebimento na doca — operações logísticas
# --------------------------------------------------------------------------------------

def recebimento_doca() -> dict:
    itens_veiculo = [
        ("bau_limpo", "Baú limpo e sem odor", ""),
        ("bau_seco", "Baú seco, sem infiltração", "Verifique teto e cantos"),
        ("assoalho", "Assoalho sem furos ou pregos expostos", ""),
        ("pragas", "Ausência de sinais de pragas", ""),
    ]
    itens_carga = [
        ("amarracao", "Carga amarrada e estável", ""),
        ("paletes", "Paletes em bom estado", "Sem tábuas quebradas"),
        ("embalagens", "Embalagens íntegras", "Sem amassados, rasgos ou umidade"),
        ("etiquetas", "Etiquetas legíveis", ""),
    ]
    todos = [n for n, _, _ in itens_veiculo + itens_carga]

    survey = [
        *metadados(),
        q("note", "intro", "**Inspeção de recebimento**\n\nUse na chegada do veículo, antes "
          "de iniciar a descarga."),
        *grupo("chegada", "Chegada do veículo", [
            q("select_one doca", "doca", "Doca", required="yes"),
            q("text", "transportadora", "Transportadora", required="yes"),
            q("text", "placa", "Placa do veículo", required="yes", constraint=REGEX_PLACA,
              constraint_message="Placa inválida. Use o padrão ABC1234 ou ABC1D23."),
            q("text", "motorista", "Nome do motorista", required="yes"),
            q("select_one tipo_carga", "tipo_carga", "Tipo de carga", required="yes"),
            q("decimal", "temperatura", "Temperatura do baú (°C)", required="yes",
              relevant="${tipo_carga} = 'refrigerada'",
              constraint=". >= -30 and . <= 30", constraint_message="Temperatura fora da faixa."),
        ]),
        q("begin_repeat", "notas", "Notas fiscais"),
        q("text", "nota_numero", "Número da nota fiscal", required="yes",
          constraint="regex(., '^[0-9]{1,9}$')", constraint_message="Apenas números."),
        q("integer", "nota_volumes", "Volumes previstos na nota", required="yes",
          constraint=". > 0"),
        q("end_repeat", "notas"),
        *grupo("lacre", "Lacre", [
            q("select_one sim_nao", "lacre_integro", "Lacre íntegro?", required="yes",
              appearance="horizontal-compact"),
            q("text", "lacre_numero", "Número do lacre"),
            q("image", "lacre_foto", "Foto do lacre", required="yes", appearance="new"),
        ]),
        *grupo("veiculo", "Condições do veículo",
               [linha for n, r, d in itens_veiculo for linha in item_checklist(n, r, d)]),
        *grupo("carga", "Condições da carga",
               [linha for n, r, d in itens_carga for linha in item_checklist(n, r, d)]),
        *grupo("conferencia", "Conferência de volumes", [
            q("calculate", "volumes_previstos", calculation="sum(${nota_volumes})"),
            q("integer", "volumes_recebidos", "Volumes recebidos (contagem física)",
              required="yes", constraint=". >= 0"),
            q("calculate", "divergencia", calculation="${volumes_recebidos} - ${volumes_previstos}"),
            q("note", "aviso_divergencia",
              "**Atenção:** divergência de ${divergencia} volume(s) em relação às notas.",
              relevant="${divergencia} != 0"),
            q("text", "divergencia_obs", "Explique a divergência", required="yes",
              relevant="${divergencia} != 0", appearance="multiline"),
        ]),
        *grupo("decisao", "Decisão", [
            q("calculate", "qtd_nao_conformes", calculation=contar_nao_conformes(todos)),
            q("select_one resultado", "resultado", "Resultado do recebimento", required="yes"),
            q("text", "motivo_recusa", "Motivo da recusa", required="yes",
              relevant="${resultado} = 'recusado'", appearance="multiline"),
            q("text", "conferente", "Nome do conferente", required="yes"),
            q("image", "assinatura_motorista", "Assinatura do motorista", required="yes",
              appearance="signature"),
        ]),
    ]
    choices = [
        *ESCOLHAS_CONFORMIDADE,
        ("sim_nao", "sim", "Sim"),
        ("sim_nao", "nao", "Não"),
        *[("doca", f"doca_{i:02d}", f"Doca {i:02d}") for i in range(1, 9)],
        ("tipo_carga", "seca", "Seca"),
        ("tipo_carga", "refrigerada", "Refrigerada"),
        ("tipo_carga", "perigosa", "Produto perigoso"),
        ("resultado", "aprovado", "Aprovado"),
        ("resultado", "aprovado_ressalva", "Aprovado com ressalva"),
        ("resultado", "recusado", "Recusado"),
    ]
    settings = {
        "form_title": "Inspeção de recebimento na doca",
        "form_id": "recebimento_doca",
        "version": "2026112001",
        "instance_name": "concat(jr:choice-name(${doca}, '${doca}'), ' - ', ${placa}, ' - ', format-date(today(), '%d/%m/%Y'))",
        "default_language": "pt",
    }
    return {"arquivo": "recebimento_doca.xlsx", "survey": survey, "choices": choices,
            "settings": settings}


# --------------------------------------------------------------------------------------
# 3. Inspeção de manutenção industrial
# --------------------------------------------------------------------------------------

def manutencao_industrial() -> dict:
    itens = [
        ("protecoes", "Proteções e grades de segurança instaladas", ""),
        ("emergencia", "Botão de emergência funcionando", "Teste com a máquina parada"),
        ("lubrificacao", "Lubrificação", "Nível e pontos de graxa"),
        ("ruido", "Ruído normal", ""),
        ("vibracao", "Vibração normal", ""),
        ("vazamentos", "Sem vazamentos (óleo, ar, água)", ""),
        ("eletrica", "Cabos e conexões elétricas", "Sem fios expostos ou aquecidos"),
        ("limpeza", "Limpeza da área e do equipamento", ""),
    ]
    todos = [n for n, _, _ in itens]

    survey = [
        *metadados(),
        q("note", "intro", "**Inspeção de manutenção**\n\nAntes de começar, confirme o "
          "bloqueio e a etiquetagem do equipamento."),
        *grupo("equipamento", "Equipamento", [
            q("barcode", "tag", "TAG do equipamento",
              hint="Leia o QR Code da placa do equipamento ou digite a TAG", required="yes"),
            q("select_one setor", "setor", "Setor", required="yes"),
            q("select_one tipo_manutencao", "tipo_manutencao", "Tipo de manutenção",
              required="yes"),
            q("text", "ordem_servico", "Nº da ordem de serviço"),
            q("image", "foto_antes", "Foto do equipamento antes", required="yes",
              appearance="new"),
        ]),
        *grupo("seguranca", "Segurança", [
            q("select_one sim_nao", "loto", "Bloqueio e etiquetagem (LOTO) aplicados?",
              required="yes", appearance="horizontal-compact",
              constraint=". = 'sim'",
              constraint_message="Não continue sem bloquear e etiquetar o equipamento."),
            q("select_multiple epi", "epi", "EPIs utilizados", required="yes",
              appearance="minimal"),
        ]),
        *grupo("itens", "Itens de inspeção",
               [linha for n, r, d in itens for linha in item_checklist(n, r, d)]),
        *grupo("medicoes", "Medições", [
            q("decimal", "temperatura_mancal", "Temperatura do mancal (°C)",
              hint="Termômetro infravermelho", constraint=". >= -20 and . <= 200",
              constraint_message="Valor fora da faixa de medição."),
            q("note", "alerta_temperatura",
              "**Atenção:** temperatura acima de 80 °C. Registre como não conformidade.",
              relevant="${temperatura_mancal} > 80"),
            q("decimal", "horimetro", "Horímetro (h)", constraint=". >= 0"),
        ]),
        *grupo("encerramento", "Encerramento", [
            q("calculate", "qtd_nao_conformes", calculation=contar_nao_conformes(todos)),
            q("select_one condicao_final", "resultado", "Condição de liberação", required="yes"),
            q("text", "restricao", "Qual a restrição ou o motivo da parada?", required="yes",
              relevant="${resultado} != 'liberado'", appearance="multiline"),
            q("text", "pecas", "Peças trocadas ou necessárias", appearance="multiline"),
            q("image", "foto_depois", "Foto do equipamento depois", required="yes",
              appearance="new"),
            q("text", "tecnico", "Nome do técnico", required="yes"),
            q("image", "assinatura_tecnico", "Assinatura do técnico", required="yes",
              appearance="signature"),
        ]),
    ]
    choices = [
        *ESCOLHAS_CONFORMIDADE,
        ("sim_nao", "sim", "Sim"),
        ("sim_nao", "nao", "Não"),
        ("setor", "usinagem", "Usinagem"),
        ("setor", "estamparia", "Estamparia"),
        ("setor", "montagem", "Montagem"),
        ("setor", "embalagem", "Embalagem"),
        ("setor", "utilidades", "Utilidades (compressores, caldeiras)"),
        ("tipo_manutencao", "preventiva", "Preventiva"),
        ("tipo_manutencao", "corretiva", "Corretiva"),
        ("tipo_manutencao", "preditiva", "Preditiva"),
        ("epi", "oculos", "Óculos"),
        ("epi", "luvas", "Luvas"),
        ("epi", "protetor_auricular", "Protetor auricular"),
        ("epi", "botina", "Botina"),
        ("epi", "capacete", "Capacete"),
        ("condicao_final", "liberado", "Liberado"),
        ("condicao_final", "liberado_restricao", "Liberado com restrição"),
        ("condicao_final", "parado", "Parado aguardando reparo"),
    ]
    settings = {
        "form_title": "Inspeção de manutenção industrial",
        "form_id": "manutencao_industrial",
        "version": "2026112001",
        "instance_name": "concat(${tag}, ' - ', jr:choice-name(${tipo_manutencao}, '${tipo_manutencao}'), ' - ', format-date(today(), '%d/%m/%Y'))",
        "default_language": "pt",
    }
    return {"arquivo": "manutencao_industrial.xlsx", "survey": survey, "choices": choices,
            "settings": settings}


FORMULARIOS = [vistoria_veiculo, recebimento_doca, manutencao_industrial]


def salvar_xlsx(definicao: dict, destino: Path) -> Path:
    wb = Workbook()
    negrito = Font(bold=True)
    fundo = PatternFill("solid", fgColor="DDEBF7")

    def aba(ws, colunas, linhas):
        ws.append(colunas)
        for c in ws[1]:
            c.font, c.fill = negrito, fundo
        for linha in linhas:
            ws.append([linha.get(col, "") for col in colunas])
        ws.freeze_panes = "A2"
        for i, col in enumerate(colunas, start=1):
            largura = max(len(str(ws.cell(r, i).value or "")) for r in range(1, ws.max_row + 1))
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(max(largura, 10), 60)

    aba(wb.active, COLUNAS_SURVEY, definicao["survey"])
    wb.active.title = "survey"
    aba(wb.create_sheet("choices"), COLUNAS_CHOICES,
        [dict(zip(COLUNAS_CHOICES, c)) for c in definicao["choices"]])
    aba(wb.create_sheet("settings"), COLUNAS_SETTINGS, [definicao["settings"]])

    caminho = destino / definicao["arquivo"]
    wb.save(caminho)
    return caminho


def validar(caminho: Path) -> None:
    from pyxform.xls2xform import convert

    # validate=True roda também o ODK Validate (exige Java instalado)
    resultado = convert(xlsform=str(caminho), validate=True)
    for aviso in resultado.warnings:
        print(f"  aviso: {aviso}")
    print(f"  válido: {caminho.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--validar", action="store_true", help="valida com o pyxform")
    args = parser.parse_args()

    for fabrica in FORMULARIOS:
        caminho = salvar_xlsx(fabrica(), PASTA)
        print(f"gerado: {caminho.relative_to(PASTA.parent)}")
        if args.validar:
            validar(caminho)


if __name__ == "__main__":
    main()
