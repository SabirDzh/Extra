from sqladmin import ModelView

from core.models import User


class UserAdmin(ModelView, model=User):
    """Expose user records for support without credential or role mutation."""

    column_list = [
        User.id,
        User.email,
        User.fullname,
        User.role,
        User.is_active,
        User.is_verified,
    ]
    can_create = False
    can_edit = False
    can_delete = False
    form_excluded_columns = [
        User.hashed_password,
        User.access_tokens,
        User.is_superuser,
        User.role,
    ]
