from dataclasses import dataclass


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True)
class Actor:
    """The authenticated caller, as the services need it (built from the Keycloak RequestContext)."""

    user_id: str
    email: str = ""
