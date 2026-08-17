from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./soc.db"

    m365_tenant_id: str = ""
    m365_client_id: str = ""
    m365_client_secret: str = ""
    m365_content_types: str = "Audit.AzureActiveDirectory,Audit.Exchange,Audit.General"
    m365_poll_interval_seconds: int = 300

    fortinet_syslog_host: str = "0.0.0.0"
    fortinet_syslog_port: int = 5514
    fortinet_syslog_protocol: str = "udp"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    alert_from_address: str = "soc-alerts@example.com"
    alert_internal_recipients: str = ""
    alert_cooldown_minutes: int = 30

    @property
    def m365_content_type_list(self) -> list[str]:
        return [c.strip() for c in self.m365_content_types.split(",") if c.strip()]

    @property
    def alert_internal_recipient_list(self) -> list[str]:
        return [c.strip() for c in self.alert_internal_recipients.split(",") if c.strip()]


settings = Settings()
