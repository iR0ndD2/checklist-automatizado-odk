# Imagem do integrador. O contexto de build é a raiz do repositório (ver docker-compose.yml).
FROM python:3.12-slim

# Bibliotecas de sistema que o WeasyPrint usa para gerar o PDF
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Sao_Paulo

WORKDIR /projeto/integrador
COPY integrador/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY formularios/*.xlsx /projeto/formularios/
COPY exemplos /projeto/exemplos
COPY integrador /projeto/integrador

# Roda sem privilégios de administrador
RUN useradd --create-home integrador && mkdir -p /projeto/saida && chown integrador /projeto/saida
USER integrador

CMD ["python", "-m", "app", "agendar"]
