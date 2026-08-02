from app.permissions.service import ROLE_PERMISSIONS


def test_elevated_roles_include_editor_permissions():
    assert ROLE_PERMISSIONS["editor"] <= ROLE_PERMISSIONS["admin"]
    assert ROLE_PERMISSIONS["admin"] <= ROLE_PERMISSIONS["owner"]
