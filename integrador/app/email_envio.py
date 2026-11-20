"""Envio do relatório por e-mail (SMTP)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from .config import Config


def enviar(config: Config, destinatarios: list[str], assunto: str, corpo_html: str,
           anexo: Path) -> None:
    mensagem = EmailMessage()
    mensagem["From"] = config.remetente
    mensagem["To"] = ", ".join(destinatarios)
    mensagem["Subject"] = assunto
    mensagem.set_content("Seu leitor de e-mail não exibe HTML. O relatório está em anexo.")
    mensagem.add_alternative(corpo_html, subtype="html")
    mensagem.add_attachment(anexo.read_bytes(), maintype="application", subtype="pdf",
                            filename=anexo.name)

    with smtplib.SMTP(config.smtp_host, config.smtp_porta, timeout=30) as smtp:
        if config.smtp_tls:
            smtp.starttls()
        if config.smtp_usuario:
            smtp.login(config.smtp_usuario, config.smtp_senha)
        smtp.send_message(mensagem)


def corpo(titulo: str, identificacao: str, resultado: str, qtd_nao_conformes: int,
          alerta: bool) -> str:
    cor = "#b91c1c" if alerta else "#15803d"
    situacao = "Exige providência" if alerta else "Sem pendências"
    return f"""\
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #1f2937">
  <p>Uma nova inspeção foi registrada.</p>
  <table style="border-collapse: collapse">
    <tr><td style="padding: 2px 12px 2px 0; color: #6b7280">Formulário</td><td>{titulo}</td></tr>
    <tr><td style="padding: 2px 12px 2px 0; color: #6b7280">Identificação</td><td>{identificacao}</td></tr>
    <tr><td style="padding: 2px 12px 2px 0; color: #6b7280">Resultado</td><td>{resultado}</td></tr>
    <tr><td style="padding: 2px 12px 2px 0; color: #6b7280">Não conformidades</td><td>{qtd_nao_conformes}</td></tr>
    <tr><td style="padding: 2px 12px 2px 0; color: #6b7280">Situação</td>
        <td style="color: {cor}; font-weight: bold">{situacao}</td></tr>
  </table>
  <p>O relatório completo, com fotos e assinatura, está em anexo.</p>
  <p style="color: #9ca3af; font-size: 12px">Mensagem automática. Não responda.</p>
</div>"""
