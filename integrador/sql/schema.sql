-- Estrutura do banco do integrador. Pode rodar várias vezes: só cria o que não existe.

CREATE TABLE IF NOT EXISTS submissao (
    instance_id     TEXT PRIMARY KEY,               -- id único da resposta no ODK
    form_id         TEXT        NOT NULL,
    enviado_em      TIMESTAMPTZ NOT NULL,           -- quando chegou ao ODK Central
    enviado_por     TEXT,
    resultado       TEXT,                            -- campo "resultado" do formulário
    qtd_nao_conformes INTEGER   NOT NULL DEFAULT 0,
    alerta          BOOLEAN     NOT NULL DEFAULT FALSE,
    dados           JSONB       NOT NULL,           -- resposta completa, como veio da API
    status          TEXT        NOT NULL DEFAULT 'pendente'
                    CHECK (status IN ('pendente', 'enviado', 'erro')),
    tentativas      INTEGER     NOT NULL DEFAULT 0,
    ultimo_erro     TEXT,
    arquivo_pdf     TEXT,
    recebido_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    processado_em   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_submissao_status ON submissao (status);
CREATE INDEX IF NOT EXISTS ix_submissao_form_data ON submissao (form_id, enviado_em);

-- Marca até onde cada formulário já foi lido, para a próxima carga ser incremental
CREATE TABLE IF NOT EXISTS controle_carga (
    form_id         TEXT PRIMARY KEY,
    ultima_data     TIMESTAMPTZ NOT NULL,
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Histórico de e-mails enviados (auditoria)
CREATE TABLE IF NOT EXISTS envio_email (
    id              BIGSERIAL PRIMARY KEY,
    instance_id     TEXT        NOT NULL REFERENCES submissao (instance_id),
    destinatarios   TEXT[]      NOT NULL,
    assunto         TEXT        NOT NULL,
    enviado_em      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Visão pronta para painéis e planilhas: uma linha por inspeção
CREATE OR REPLACE VIEW vw_inspecoes AS
SELECT
    form_id,
    instance_id,
    enviado_em,
    enviado_por,
    resultado,
    qtd_nao_conformes,
    alerta,
    status
FROM submissao;
