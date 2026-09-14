# Деплой: nginx на VM

Compose: `nginx` (80), `app` (8000 только localhost), `qdrant`.

GitHub Actions собирает образ в GHCR и по SSH делает `docker compose pull && up -d`. VM не собирает зависимости.

Секреты RouterAI лежат в `/opt/creditlens/.env` на сервере, не в GitHub Actions.

TLS-серверблок: `deploy/nginx/creditlens.ssl.conf.example`. Домен добавляется позже без смены приложения.

![CI/CD](../screenshots/diagrams/cicd-nginx-vm.png)
