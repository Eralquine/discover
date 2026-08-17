# log-ingestion-alerts

Herramienta lista para **recibir logs de Microsoft 365 (correo/Entra ID) y de un
firewall Fortinet**, normalizarlos en un esquema común, evaluar reglas de
detección de actividad sospechosa y **enviar alertas por correo** — tanto a tu
equipo interno como, opcionalmente, **reenviadas a un cliente**. Pensada para
correr de forma remota y automática (un proceso siempre activo, sin
intervención manual).

## Arquitectura

```
                 ┌────────────────────────┐
Microsoft 365 ──▶│  Poller M365 (Office365 │
(Entra ID,       │  Management Activity    │──┐
Exchange, ...)    API, cada 5 min)         │  │
                 └────────────────────────┘  │
                                              ▼
                                        ┌───────────┐      ┌────────────┐      ┌─────────────┐
FortiGate ───syslog UDP/TCP───────────▶│  Cola de   │────▶│ Normalizar +│────▶│  Motor de    │
(remote logging)                       │  ingesta   │     │  guardar en │     │  reglas      │
                                        └───────────┘      │  Postgres   │     └──────┬───────┘
                                                            └────────────┘            │
                                                                                       ▼
                                                                              ┌──────────────────┐
                                                                              │ Alertas por email │
                                                                              │ (equipo interno + │
                                                                              │ clientes)         │
                                                                              └──────────────────┘
```

- `app/connectors/m365.py`: obtiene logs de Microsoft 365 mediante la
  **Office 365 Management Activity API** (la API que Microsoft ofrece
  específicamente para alimentar SIEMs: cubre inicios de sesión de Entra ID,
  auditoría de Exchange/reglas de reenvío de correo, SharePoint, etc. en un
  solo feed).
- `app/connectors/fortinet_syslog.py`: levanta un listener de **syslog**
  (UDP o TCP) donde apuntas el "remote logging" del FortiGate.
- `app/normalize.py`: convierte ambos formatos a un evento común
  (`NormalizedEvent`): fuente, tipo, severidad, actor, IP origen/destino,
  país, etc.
- `app/rules.py` + `app/rules.yaml`: reglas de detección (fuerza bruta,
  reenvío de correo externo activado, malware bloqueado, IPS, VPN, etc.),
  editables sin tocar código.
- `app/alerting.py`: arma y envía el correo de alerta por SMTP al equipo
  interno y a los clientes que correspondan.
- `app/db.py`: persistencia (SQLAlchemy — funciona con SQLite para
  pruebas locales o Postgres en producción).

## ¿Dónde vive la información? (propuesta)

Como pediste que propusiera el lugar:

- **Base de datos**: Postgres administrado. La opción más simple para tener
  algo "en internet" sin operar tú un servidor de base de datos es un
  proyecto gratuito en **[Supabase](https://supabase.com)** (Postgres
  administrado, capa gratuita generosa) — solo cambias `DATABASE_URL` en
  `.env`. Si prefieres no depender de un tercero, `docker-compose.yml` ya
  incluye un contenedor Postgres para correrlo tú mismo en un VPS.
- **Cómputo (donde corre la herramienta)**: necesita estar *siempre
  encendida* porque escucha syslog en un puerto propio y hace polling
  periódico a Microsoft 365. Recomiendo un **VPS pequeño y económico**
  (DigitalOcean, Hetzner, Lightsail, etc., 1 vCPU/1GB alcanza) donde
  despliegas con `docker compose up -d`. Evita plataformas "serverless" para
  la parte de syslog: necesitas un puerto UDP/TCP siempre abierto, cosa que
  el modelo serverless clásico no ofrece bien.
- En producción, protege el puerto de syslog: usa TCP+TLS si tu firmware de
  FortiGate lo soporta, y restringe por firewall el origen a la IP pública
  del FortiGate.

## Configuración de Microsoft 365

1. En Entra ID (Azure AD) → **App registrations** → crea una app.
2. **API permissions** → Add a permission → **Office 365 Management APIs**
   → Application permissions → `ActivityFeed.Read` → **Grant admin
   consent**.
3. En **Certificates & secrets**, crea un client secret.
4. Copia `Tenant ID`, `Application (client) ID` y el secret a tu `.env`
   (`M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET`).
5. La primera vez que corre, la herramienta inicia automáticamente las
   suscripciones a los tipos de contenido listados en
   `M365_CONTENT_TYPES` (auditoría de Azure AD, Exchange y general —
   incluye creación de reglas de reenvío de correo, cambios de roles
   privilegiados, inicios de sesión fallidos, etc.).

## Configuración del FortiGate

En el FortiGate: **Log & Report → Log Settings → Remote Logging** (o
**Security Fabric → External Connectors → Syslog** según la versión de
firmware), apunta al host/puerto donde corre esta herramienta
(`FORTINET_SYSLOG_HOST`/`FORTINET_SYSLOG_PORT`, por defecto UDP 5514). Para
mayor fiabilidad en producción, usa syslog sobre TCP con TLS si el firmware
lo permite (`FORTINET_SYSLOG_PROTOCOL=tcp`).

## Reglas de detección incluidas

Editables en `app/rules.yaml` sin tocar código:

| Regla | Fuente | Dispara cuando |
|---|---|---|
| `m365_brute_force` | M365 | ≥5 inicios de sesión fallidos del mismo usuario en 10 min |
| `m365_mailbox_forwarding` | M365 | Se activa reenvío externo de correo (indicador clásico de BEC) |
| `m365_inbox_rule` | M365 | Se crea/modifica una regla de bandeja de entrada |
| `m365_privileged_role` | M365 | Se asigna un rol privilegiado |
| `m365_mail_threat` | M365 | Defender detecta una amenaza de correo |
| `fortinet_scan` | Fortinet | ≥50 conexiones denegadas desde el mismo origen en 5 min |
| `fortinet_malware` | Fortinet | El FortiGate bloquea malware |
| `fortinet_ips_block` | Fortinet | El IPS bloquea un ataque |
| `fortinet_vpn_bruteforce` | Fortinet | ≥5 logins VPN fallidos desde el mismo origen en 10 min |

Cada alerta se enfría (`ALERT_COOLDOWN_MINUTES`, 30 min por defecto) para no
saturar el correo mientras el mismo problema sigue activo.

## Reenvío a clientes

Registra un cliente (opcionalmente limitado a una sola fuente) y sus
correos de contacto:

```bash
python -m scripts.add_client --name "Cliente Demo" --emails soc@cliente.com,ciso@cliente.com
# Solo alertas de Fortinet para este cliente:
python -m scripts.add_client --name "Cliente Demo" --emails soc@cliente.com --source fortinet
```

Cada alerta que dispare una regla se envía siempre a
`ALERT_INTERNAL_RECIPIENTS` y además a todos los clientes activos que
apliquen.

## Puesta en marcha

```bash
cp .env.example .env
# completa las credenciales de M365, SMTP, etc.

# Local / pruebas (SQLite):
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main

# Producción (Postgres + contenedor siempre activo):
docker compose up -d --build
```

## Pruebas

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest
```

Las pruebas (`tests/`) usan fixtures de logs reales de M365 y FortiGate y
una base de datos SQLite en memoria — no requieren credenciales ni acceso a
internet.

## Qué falta para producción real

- Credenciales reales de Microsoft 365 y acceso de red desde el FortiGate
  hacia el host donde corra esto (no puedo generarlas ni probarlas por ti).
- Un servidor SMTP para el envío de correo (puede ser el propio Microsoft
  365, SendGrid, Resend, etc.).
- Revisar los umbrales de `rules.yaml` con tráfico real de tu entorno antes
  de confiar en ellos para no generar demasiados falsos positivos.
