# Deploy na Railway

Este guia prepara o projeto, mas não cria recursos nem realiza deploy. No dashboard
da Railway, crie um único projeto com exatamente três serviços:

- `backend`, conectado ao repositório `reicoastdev/back-joeleeli`;
- `frontend`, conectado ao repositório `reicoastdev/front-joeleeli`;
- `Postgres`, criado pelo template oficial da Railway.

Não crie Redis, worker, cron, volume de mídia, Nginx ou outro serviço neste
incremento.

## Ordem no dashboard

Siga esta sequência para que as referências de domínio existam antes de serem
consumidas:

1. Crie o projeto Railway com o nome `Joeleeli`.
2. Crie o serviço PostgreSQL.
3. Crie o serviço do backend a partir do GitHub.
4. Nomeie esse serviço exatamente `backend`.
5. Configure as variáveis essenciais do backend listadas abaixo.
6. Faça o primeiro deploy do backend.
7. Gere o domínio público do backend.
8. Crie o serviço do frontend a partir do GitHub.
9. Nomeie esse serviço exatamente `frontend`.
10. Configure `VITE_API_BASE_URL=https://${{backend.RAILWAY_PUBLIC_DOMAIN}}`.
11. Faça o primeiro deploy do frontend.
12. Gere o domínio público do frontend.
13. Configure no backend
    `CORS_ALLOWED_ORIGINS=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}` e
    `CSRF_TRUSTED_ORIGINS=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}`.
14. Faça redeploy do backend.
15. Se a URL pública do backend não estava disponível durante o primeiro build,
    faça redeploy do frontend.
16. Execute a validação ponta a ponta descrita neste guia.

## 1. Serviço Postgres

No projeto, use **New > Database > Add PostgreSQL**. Mantenha o serviço privado; o
backend acessará sua `DATABASE_URL` por referência entre serviços.

## 2. Serviço backend

Crie um serviço a partir do repositório do backend e selecione a branch desejada. O
`railway.json` versionado seleciona o `Dockerfile`, executa migrations antes de cada
release e usa `/api/v1/health/` como healthcheck. O container inicia Gunicorn em
`${PORT:-8000}` e coleta os arquivos estáticos durante o build.

Configure estas variáveis no serviço:

```text
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<GERAR_UM_SEGREDO_FORTE_E_EXCLUSIVO>
DJANGO_DEBUG=False
DATABASE_URL=${{Postgres.DATABASE_URL}}
DJANGO_ALLOWED_HOSTS=${{backend.RAILWAY_PUBLIC_DOMAIN}}
CORS_ALLOWED_ORIGINS=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}
CSRF_TRUSTED_ORIGINS=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}
```

`RAILWAY_PUBLIC_DOMAIN` e `RAILWAY_PRIVATE_DOMAIN` são disponibilizadas pela
plataforma. As settings adicionam ambas, quando presentes, e o host dedicado dos
healthchecks à allowlist; nenhum wildcard é aceito. Gere um domínio público para o
backend em **Settings > Networking > Public Networking**.

## 3. Serviço frontend

Conecte o repositório do frontend. Seu `railway.json` usa o `Dockerfile` e verifica
`GET /health`. Configure a variável abaixo no serviço antes do build:

```text
VITE_API_BASE_URL=https://${{backend.RAILWAY_PUBLIC_DOMAIN}}
```

Variáveis `VITE_*` são incorporadas ao bundle no build; alterá-las exige redeploy.
Gere também um domínio público para o frontend. O acesso a um convite usa
`https://<frontend>/rsvp#TOKEN`: o fragmento permanece no navegador, e o frontend
envia a credencial ao backend exclusivamente no header `Authorization: Bearer`.

## 4. Primeiro deploy e validação

Depois de revisar todas as variáveis, faça o deploy dos serviços. A etapa pre-deploy
do backend executará:

```text
uv run --no-sync python manage.py migrate --noinput
```

Valide no domínio público:

- `GET https://<backend>/api/v1/health/` retorna `{"status":"ok"}`;
- `/admin/` carrega CSS e JavaScript sem 404;
- `GET https://<frontend>/health` retorna 200;
- atualizar `https://<frontend>/rsvp#TOKEN` mantém a SPA;
- requests RSVP usam `/api/v1/public/rsvp/`, nunca incluem o token no path e não
  deixam a credencial nos logs.

## 5. Domínios customizados

Ao trocar os domínios Railway por domínios próprios:

1. cadastre os novos domínios em cada serviço;
2. altere `VITE_API_BASE_URL` para o domínio público definitivo do backend;
3. altere `CORS_ALLOWED_ORIGINS` e `CSRF_TRUSTED_ORIGINS` para o domínio público
   definitivo do frontend;
4. se necessário, inclua o domínio do backend em `DJANGO_ALLOWED_HOSTS`;
5. faça redeploy do frontend e do backend e repita os healthchecks.

Separe múltiplas origens ou hosts por vírgula, sem usar `*`.
