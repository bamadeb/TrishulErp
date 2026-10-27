"""Cognito identifiers sourced from AWS Secrets Manager.

The secret holds the public Cognito identifiers in JSON::

    {"region": "us-east-1", "userPoolId": "us-east-1_xxxx", "appClientId": "xxxx"}

These are not confidential (the browser receives them in config.json); the secret just centralises
configuration the way the DB secret does. ``apply_cognito_secret`` fills the settings from it at startup,
with the environment values used as a fallback for any field the secret omits.
"""

from trishul_api.config import Settings
from trishul_api.secrets import SecretProvider


def apply_cognito_secret(settings: Settings, provider: SecretProvider) -> Settings:
    """Return settings with the Cognito region, user pool id and app client id taken from the secret.

    If ``cognito_secret_id`` is not set, or auth is not Cognito, the settings are returned unchanged.
    """
    if not settings.cognito_secret_id or settings.auth_mode != "cognito":
        return settings
    data = provider.get_json(settings.cognito_secret_id)
    return settings.model_copy(
        update={
            "cognito_region": str(data.get("region") or settings.cognito_region),
            "cognito_user_pool_id": str(data.get("userPoolId") or settings.cognito_user_pool_id),
            "cognito_app_client_id": str(data.get("appClientId") or settings.cognito_app_client_id),
        }
    )
