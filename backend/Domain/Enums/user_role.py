from enum import StrEnum


class UserRole(StrEnum):
    user = "user"
    admin = "administrator"
    manager = "manager"
    client = "client"
