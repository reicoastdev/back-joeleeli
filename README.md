# back-joeleeli

Backend API-first para gestão de convidados e check-in de eventos. Este bootstrap usa
Python, Django, Django REST Framework e PostgreSQL em uma arquitetura de monólito
modular.

## Requisitos

- Python 3.12 a 3.14;
- [uv](https://docs.astral.sh/uv/);
- PostgreSQL 17 ou compatível;
- Docker e Docker Compose (opcional para execução conteinerizada).

## Instalação local

```bash
cp .env.example .env
uv sync --frozen
```

Revise o `DATABASE_URL` do `.env` antes de prosseguir. A aplicação usa PostgreSQL;
SQLite não é configurado como fallback.

Para iniciar apenas o PostgreSQL fornecido pelo Compose e executar a aplicação no
host:

```bash
docker compose up -d db
uv run python manage.py migrate
uv run python manage.py runserver
```

A API ficará disponível em `http://localhost:8000`.

## Docker

Suba PostgreSQL e aplicação com um único comando:

```bash
docker compose up --build
```

O serviço aguarda o PostgreSQL ficar saudável, aplica migrations e inicia o servidor
de desenvolvimento. Pare o ambiente com `docker compose down`. Os dados do banco e
o ambiente virtual do container ficam em volumes nomeados.

## Comandos operacionais

```bash
# migrations
uv run python manage.py migrate
uv run python manage.py makemigrations --check

# usuário administrativo
uv run python manage.py createsuperuser

# qualidade e testes
make lint
make format-check
make format
make test
make check
```

Os testes usam o PostgreSQL indicado por `DATABASE_URL`. Com o banco do Compose em
execução, o pytest cria e remove seu próprio banco de teste de forma isolada.

## API e documentação

- Health check: `GET /api/v1/health/`;
- schema OpenAPI: `GET /api/schema/`;
- Swagger UI: `GET /api/docs/`;
- Django Admin: `/admin/`.

Novos endpoints de negócio devem ser adicionados sob `/api/v1/`.

## Configuração

O arquivo `.env.example` documenta as variáveis locais. O `.env` real é ignorado pelo
Git. Em produção, use `DJANGO_SETTINGS_MODULE=config.settings.production`; nessa
configuração, `DJANGO_SECRET_KEY`, `DATABASE_URL` e `DJANGO_ALLOWED_HOSTS` são
obrigatórios e a inicialização falha explicitamente quando estiverem ausentes.

`CORS_ALLOWED_ORIGINS` e `CSRF_TRUSTED_ORIGINS` aceitam listas separadas por vírgula.
Não há liberação global de CORS.
