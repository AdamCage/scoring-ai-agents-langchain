#!/usr/bin/env bash
# Install credit-adamcage.ru on the Timeweb VM and issue Let's Encrypt.
# Love AI on 80/443 default_server is left untouched.
set -euo pipefail

DOMAIN="${DOMAIN:-credit-adamcage.ru}"
WWW="www.${DOMAIN}"
EXPECTED_IP="${EXPECTED_IP:-31.130.128.81}"
REPO="${REPO:-/opt/creditlens}"
EMAIL="${CERTBOT_EMAIL:-}"

if [[ $(id -u) -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

install -d -m 0755 /var/www/certbot
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx

cp "${REPO}/deploy/nginx/credit-adamcage.ru.http.conf" /etc/nginx/sites-available/credit-adamcage.ru
ln -sfn /etc/nginx/sites-available/credit-adamcage.ru /etc/nginx/sites-enabled/credit-adamcage.ru
nginx -t
systemctl reload nginx

resolve_a() {
  python3 - "${DOMAIN}" <<'PY'
import json, sys, urllib.request
name = sys.argv[1]
url = f"https://cloudflare-dns.com/dns-query?name={name}&type=A"
req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
try:
    data = json.load(urllib.request.urlopen(req, timeout=10))
except Exception as exc:
    print("ERROR", exc)
    raise SystemExit(2)
if data.get("Status") != 0:
    print("NXDOMAIN")
    raise SystemExit(3)
answers = [item["data"] for item in data.get("Answer") or [] if item.get("type") == 1]
print(" ".join(answers) if answers else "NONE")
PY
}

echo "DNS A ${DOMAIN}: $(resolve_a || true)"
A_RECORDS="$(resolve_a || true)"
if [[ "${A_RECORDS}" != *"${EXPECTED_IP}"* ]]; then
  cat <<EOF
A-запись ${DOMAIN} сейчас: ${A_RECORDS}
Нужно: ${EXPECTED_IP}  (эта VM, Timeweb, CreditLens)
95.163.244.138 — общий IP REG.RU, не этот сервер. HTTP-01 Let's Encrypt туда не дойдёт.
Исправьте A на ${EXPECTED_IP} и запустите скрипт снова.
EOF
  exit 4
fi

CERTBOT_ARGS=(certonly --webroot -w /var/www/certbot -d "${DOMAIN}" --agree-tos --non-interactive)
if [[ -n "${EMAIL}" ]]; then
  CERTBOT_ARGS+=(--email "${EMAIL}")
else
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi
if getent hosts "${WWW}" >/dev/null 2>&1; then
  CERTBOT_ARGS+=(-d "${WWW}")
fi
certbot "${CERTBOT_ARGS[@]}"

cp "${REPO}/deploy/nginx/credit-adamcage.ru.conf" /etc/nginx/sites-available/credit-adamcage.ru
nginx -t
systemctl reload nginx
systemctl enable --now certbot.timer 2>/dev/null || true
echo "https://${DOMAIN} ready"
