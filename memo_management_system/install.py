import frappe
from frappe.modules.import_file import import_file_by_path

from memo_management_system.utils.memo import (
    DEFAULT_DESK_ROLES,
    cleanup_legacy_memo_artifacts,
    ensure_roles,
    setup_default_settings,
    setup_memo_workflow,
    sync_memo_roles_for_existing_employees,
    upsert_default_print_format,
)

APP_NAME = "memo_management_system"
WORKSPACE_NAME = "Memo Management"
PRINT_FORMAT_NAME = "Official Memo"


def sync_workspace_documents():
    frappe.reload_doc("memo_management_system", "workspace", "memo_management")
    frappe.reload_doc("memo_management_system", "doctype", "memo")
    frappe.reload_doc("memo_management_system", "doctype", "memo_action_point")
    frappe.reload_doc("memo_management_system", "doctype", "memo_recipient")
    frappe.reload_doc("memo_management_system", "doctype", "memo_reference")
    frappe.reload_doc("memo_management_system", "doctype", "memo_routing_log")
    frappe.reload_doc("memo_management_system", "doctype", "memo_settings")
    frappe.reload_doc("memo_management_system", "doctype", "memo_settings_role")
    frappe.reload_doc("memo_management_system", "print_format", "official_memo")
    frappe.reload_doc("memo_management_system", "report", "memo_governance_report")

    for folder_name in ("workspace_sidebar", "desktop_icon"):
        import_file_by_path(
            frappe.get_app_path(APP_NAME, folder_name, "memo_management.json"),
            ignore_version=True,
        )


def set_desk_roles():
    for doctype in ("Workspace", "Desktop Icon"):
        if not frappe.db.exists(doctype, WORKSPACE_NAME):
            continue

        doc = frappe.get_doc(doctype, WORKSPACE_NAME)
        if doctype == "Workspace" and not doc.type:
            doc.type = "Workspace"
        current_roles = [row.role for row in doc.roles]
        if current_roles == list(DEFAULT_DESK_ROLES):
            continue

        doc.set("roles", [{"role": role_name} for role_name in DEFAULT_DESK_ROLES])
        doc.save(ignore_permissions=True)


def normalize_memo_user_permission():
    """Let the controller authorize non-owner workflow writes.

    The unrestricted row lets document-shared participants reach the
    controller. Explicit document shares preserve access when link-level User
    Permissions would otherwise hide a memo from its own creator.
    """
    for name in frappe.get_all(
        "Custom DocPerm",
        filters={"parent": "Memo", "role": "Memo User", "permlevel": 0, "if_owner": 0},
        pluck="name",
    ):
        frappe.db.set_value(
            "Custom DocPerm",
            name,
            {"if_owner": 0, "read": 1, "print": 1, "share": 1},
            update_modified=False,
        )

    for name in frappe.get_all(
        "Custom DocPerm",
        filters={"parent": "Memo", "role": "Memo User", "permlevel": 0, "if_owner": 1},
        pluck="name",
    ):
        frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)

    for name in frappe.get_all("Memo", pluck="name"):
        frappe.get_doc("Memo", name)._sync_participant_shares()


def setup_workspace():
    sync_workspace_documents()
    set_desk_roles()
    frappe.clear_cache()


def after_install():
    ensure_roles()
    setup_default_settings()
    sync_memo_roles_for_existing_employees()
    setup_workspace()
    normalize_memo_user_permission()
    cleanup_legacy_memo_artifacts()
    upsert_default_print_format("Memo", PRINT_FORMAT_NAME)
    setup_memo_workflow()
    frappe.db.commit()


def after_migrate():
    ensure_roles()
    setup_default_settings()
    sync_memo_roles_for_existing_employees()
    setup_workspace()
    normalize_memo_user_permission()
    cleanup_legacy_memo_artifacts()
    upsert_default_print_format("Memo", PRINT_FORMAT_NAME)
    setup_memo_workflow()
    frappe.db.commit()
