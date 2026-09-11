from sqladmin import Admin

from admin.user import UserAdmin


def register_admin_views(admin: Admin):
    """Register the limited, authenticated SQLAdmin views."""
    admin.add_view(UserAdmin)
