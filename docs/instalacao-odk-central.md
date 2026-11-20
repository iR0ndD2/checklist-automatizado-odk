# Instalação do ODK Central

O ODK Central é o servidor que recebe as respostas enviadas pelo celular. É gratuito, de código aberto e mantido pela comunidade ODK. Este guia resume a instalação em um servidor Linux. A referência completa e sempre atualizada está na [documentação oficial](https://docs.getodk.org/central-install-digital-ocean/).

## O que você precisa

| Item | Recomendação |
|---|---|
| Servidor | Ubuntu, 2 GB de RAM (1 GB funciona com pouco volume, com 2 GB de swap) |
| Software | Docker Engine 23 ou superior e Docker Compose 2.16 ou superior |
| Domínio | Obrigatório. O Central não funciona só com o IP. Ex.: `odk.seudominio.com.br` |
| Disco | Monitore o uso: fotos se acumulam rápido. Configure um alerta perto de 90% |

Aponte o domínio para o IP do servidor (registro DNS do tipo A) antes de começar. O Central emite o certificado HTTPS sozinho, pelo Let's Encrypt.

## Passo a passo

```bash
# 1. Conferir as versões do Docker
docker --version && docker compose version

# 2. Baixar o Central
umask 022; git clone https://github.com/getodk/central
cd central
git submodule update --init

# 3. Configurar
cp .env.template .env
nano .env
#   DOMAIN=odk.seudominio.com.br      (sem http:// ou https://)
#   SYSADMIN_EMAIL=voce@seudominio.com.br

# 4. Construir e subir
docker compose build
docker compose up --detach
docker compose ps        # aguarde o central-nginx-1 ficar "Up (healthy)"

# 5. Criar o administrador
docker compose exec service odk-cmd --email voce@seudominio.com.br user-create
docker compose exec service odk-cmd --email voce@seudominio.com.br user-promote
```

Siga a documentação oficial para o firewall e para a primeira atualização do banco: os passos mudam entre versões.

## Publicar os formulários

1. Acesse `https://odk.seudominio.com.br` com o administrador.
2. Crie um projeto (ex.: "Inspeções") e anote o número dele na URL (`/projects/1`). Esse é o `ODK_PROJETO_ID` do `.env`.
3. Em **Formulários → Novo**, envie cada `.xlsx` da pasta `formularios/` e clique em **Publicar**.
4. Em **Usuários de aplicativo**, crie um usuário por equipe (pátio, doca, manutenção) e dê acesso aos formulários. Cada um gera um QR Code.
5. No celular, instale o **ODK Collect** (Android), escaneie o QR Code e pronto.

## Usuário do integrador

Crie um **usuário web** só para o integrador (não use o administrador):

1. **Usuários web → Criar**, com um e-mail próprio, por exemplo `integrador@seudominio.com.br`.
2. No projeto, em **Funções do projeto**, dê a ele a função **Visualizador de projeto**. Leitura basta.
3. Preencha `ODK_URL`, `ODK_EMAIL`, `ODK_SENHA` e `ODK_PROJETO_ID` no `.env` e troque `MODO=odk`.

## Backup

Configure os backups do Central (documentação oficial, seção *Backing up Central*). As respostas também ficam no PostgreSQL do integrador, mas as fotos originais ficam só no Central.
