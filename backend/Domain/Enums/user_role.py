from enum import StrEnum


class UserRole(StrEnum):
    admin = "administrator"
    installer = "installer"
    seller = "seller"
    serviceman = "serviceman"
    buyer = "buyer"


LEGACY_ROLE_ALIASES: dict[str, UserRole] = {
    "admin": UserRole.admin,
    "administrator": UserRole.admin,
    "user": UserRole.buyer,
    "client": UserRole.buyer,
    "manager": UserRole.seller,
    "installer": UserRole.installer,
    "seller": UserRole.seller,
    "serviceman": UserRole.serviceman,
    "buyer": UserRole.buyer,
}


def normalize_user_role(value: str | UserRole) -> UserRole:
    if isinstance(value, UserRole):
        return value
    normalized = LEGACY_ROLE_ALIASES.get(str(value).strip().lower())
    if normalized is None:
        raise ValueError(f"Unsupported role: {value}")
    return normalized
