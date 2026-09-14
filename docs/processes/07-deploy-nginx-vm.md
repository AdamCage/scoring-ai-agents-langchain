# Деплой: nginx на VM

CreditLens на Timeweb: `31.130.128.81`. systemd `creditlens` слушает `127.0.0.1:8010`.

- Порт **8080** — запасной вход по IP (`deploy/nginx/creditlens-8080.conf`).
- Домен **credit-adamcage.ru** — отдельный `server_name` на 80/443. Не `default_server`: Love AI на голом IP не трогаем.

## DNS

A-запись должна указывать на **эту VM**: `31.130.128.81`.

`95.163.244.138` — общий IP REG.RU (тысячи чужих сайтов, нет SSH). Let's Encrypt HTTP-01 туда не дойдёт.

```bash
sudo bash /opt/creditlens/scripts/setup_domain_tls.sh
```

Скрипт ставит HTTP-vhost + ACME, проверяет A, выпускает сертификат, включает HTTPS и редирект.

Секреты RouterAI только в `/opt/creditlens/.env`.

TLS-шаблон: `deploy/nginx/credit-adamcage.ru.conf`.
