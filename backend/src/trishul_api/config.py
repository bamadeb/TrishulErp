from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from environment variables prefixed TRISHUL_, or from a local .env file.

    In AWS, ECS injects the database password from Secrets Manager as TRISHUL_DB_PASSWORD.
    """

    model_config = SettingsConfigDict(env_prefix="TRISHUL_", env_file=".env", extra="ignore")

    environment: Literal["dev", "test", "uat", "prod"] = "dev"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:4200"]
    log_level: str = "INFO"

    # Database (Amazon RDS for SQL Server)
    db_host: str = "localhost"
    db_port: int = 1433
    db_name: str = "TrishulDev"
    db_user: str = ""
    db_password: SecretStr = SecretStr("")
    odbc_driver: str = "ODBC Driver 18 for SQL Server"
    db_encrypt: bool = True
    # Only for local servers with self-signed certificates; RDS certificates validate normally.
    db_trust_server_certificate: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    # Migrations run with their own login (DDL rights); the API login has data rights only.
    migration_db_user: str | None = None
    migration_db_password: SecretStr | None = None

    # AWS Secrets Manager. When db_secret_id is set, the DB username and password are read from that
    # secret (RDS JSON: {"username","password",...}) instead of TRISHUL_DB_USER/PASSWORD, and are
    # refreshed in the background so a rotated password is picked up without a restart. Leave empty for
    # local development, which uses the env values above. Only non-secret identifiers live here.
    db_secret_id: str | None = None
    migration_db_secret_id: str | None = None
    # Region for Secrets Manager; falls back to the Cognito region. Credentials come from the ECS task
    # role (the default provider chain), or from aws_profile locally — never from hardcoded keys.
    secrets_region: str | None = None
    # How long a fetched secret is cached before the next physical DB connection re-reads it.
    secrets_cache_seconds: int = 300

    # Sign-in. "dev" accepts any bearer token and acts as dev_username; never allowed in prod.
    auth_mode: Literal["cognito", "dev"] = "cognito"
    cognito_region: str = "ap-south-1"
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    # The Cognito identifiers can instead be read from a Secrets Manager secret at startup
    # (keys: region, userPoolId, appClientId). They are public identifiers (also sent to the browser),
    # so this just centralises config like the DB secret does; the values above are the fallback.
    cognito_secret_id: str | None = None
    dev_username: str = ""
    # Local development only: the AWS CLI profile for Cognito admin calls (user management).
    # In AWS the ECS task role supplies credentials, so leave it empty there.
    aws_profile: str | None = None
    # How long a user's roles and permissions are cached before re-reading core.app_user.
    user_cache_seconds: int = 60

    @property
    def cognito_issuer(self) -> str:
        return f"https://cognito-idp.{self.cognito_region}.amazonaws.com/{self.cognito_user_pool_id}"

    @property
    def aws_region(self) -> str:
        """Region for AWS SDK calls (Secrets Manager); defaults to the Cognito region."""
        return self.secrets_region or self.cognito_region

    @model_validator(mode="after")
    def _check_auth(self) -> "Settings":
        if self.auth_mode == "dev" and self.environment in ("uat", "prod"):
            raise ValueError("TRISHUL_AUTH_MODE=dev is not allowed in uat or prod")
        if (
            self.auth_mode == "cognito"
            and not self.cognito_secret_id
            and not (self.cognito_user_pool_id and self.cognito_app_client_id)
        ):
            raise ValueError(
                "Set TRISHUL_COGNITO_USER_POOL_ID and TRISHUL_COGNITO_APP_CLIENT_ID, or TRISHUL_COGNITO_SECRET_ID"
            )
        if self.auth_mode == "dev" and not self.dev_username:
            raise ValueError("Set TRISHUL_DEV_USERNAME to a core.app_user username for dev sign-in")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
