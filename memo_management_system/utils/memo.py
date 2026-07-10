import frappe


MEMO_USER_ROLE = "Memo User"
MEMO_APPROVER_ROLE = "Memo Approver"
MEMO_MANAGER_ROLE = "Memo Manager"
MEMO_ADMIN_ROLE = "Memo Administrator"

DEFAULT_GLOBAL_ACCESS_ROLES = ("System Manager", MEMO_MANAGER_ROLE, MEMO_ADMIN_ROLE)
DEFAULT_APPROVAL_ROLES = (
    "System Manager",
    MEMO_APPROVER_ROLE,
    MEMO_MANAGER_ROLE,
    MEMO_ADMIN_ROLE,
)
DEFAULT_DESK_ROLES = (
    "System Manager",
    MEMO_USER_ROLE,
    MEMO_APPROVER_ROLE,
    MEMO_MANAGER_ROLE,
    MEMO_ADMIN_ROLE,
)


def ensure_roles():
    for role_name in DEFAULT_DESK_ROLES:
        if frappe.db.exists("Role", role_name):
            continue

        frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(
            ignore_permissions=True
        )


def get_memo_settings():
    return frappe.get_single("Memo Settings")


def setup_default_settings():
    settings = get_memo_settings()
    changed = False

    defaults = {
        "auto_assign_memo_user_role": 1,
        "memo_user_role": MEMO_USER_ROLE,
        "enforce_employee_scope": 1,
        "require_approval_by_default": 1,
        "require_acknowledgement_by_default": 0,
        "enable_email_notifications": 1,
        "default_naming_series": "MEMO-.YYYY.-",
        "default_confidentiality": "Internal",
        "default_priority": "Normal",
        "default_acknowledgement_window_days": 3,
    }

    for fieldname, value in defaults.items():
        if settings.get(fieldname) in (None, ""):
            settings.set(fieldname, value)
            changed = True

    if not settings.global_access_roles:
        settings.set(
            "global_access_roles",
            [{"role": role_name} for role_name in DEFAULT_GLOBAL_ACCESS_ROLES],
        )
        changed = True

    if not settings.approval_roles:
        settings.set(
            "approval_roles",
            [{"role": role_name} for role_name in DEFAULT_APPROVAL_ROLES],
        )
        changed = True

    if changed:
        settings.save(ignore_permissions=True)


def sync_memo_access_for_employee_doc(doc, method=None):
    sync_memo_access_for_employee(doc)


def sync_memo_access_for_user_doc(doc, method=None):
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": doc.name},
        ["name", "user_id", "status"],
        as_dict=True,
    )
    if employee:
        sync_memo_access_for_employee(frappe._dict(employee))


def sync_memo_access_for_employee(employee):
    settings = get_memo_settings()
    if not settings.auto_assign_memo_user_role:
        return

    user_id = employee.user_id if hasattr(employee, "user_id") else frappe.db.get_value(
        "Employee", employee, "user_id"
    )
    employee_status = employee.status if hasattr(employee, "status") else frappe.db.get_value(
        "Employee", employee, "status"
    )
    if not user_id or employee_status == "Inactive":
        return

    ensure_user_has_role(user_id, settings.memo_user_role or MEMO_USER_ROLE)


def sync_memo_roles_for_existing_employees():
    settings = get_memo_settings()
    if not settings.auto_assign_memo_user_role:
        return

    employees = frappe.get_all(
        "Employee",
        filters={"status": ["!=", "Inactive"], "user_id": ["is", "set"]},
        fields=["name", "user_id", "status"],
        limit_page_length=0,
    )
    for employee in employees:
        sync_memo_access_for_employee(frappe._dict(employee))


def get_employee_for_user(user=None):
    user = user or frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def ensure_user_has_role(user, role):
    if not user or not role:
        return

    if frappe.db.exists("Has Role", {"parenttype": "User", "parent": user, "role": role}):
        return

    frappe.get_doc(
        {
            "doctype": "Has Role",
            "parenttype": "User",
            "parentfield": "roles",
            "parent": user,
            "role": role,
        }
    ).insert(ignore_permissions=True)
    frappe.clear_cache(user=user)


def get_global_access_roles():
    roles = [row.role for row in get_memo_settings().global_access_roles or [] if row.role]
    return roles or list(DEFAULT_GLOBAL_ACCESS_ROLES)


def get_approval_roles():
    roles = [row.role for row in get_memo_settings().approval_roles or [] if row.role]
    return roles or list(DEFAULT_APPROVAL_ROLES)


def is_employee_scope_enforced():
    return bool(get_memo_settings().enforce_employee_scope)


def has_global_access(user=None):
    user = user or frappe.session.user
    return bool(set(frappe.get_roles(user)).intersection(set(get_global_access_roles())))


def has_approval_access(user=None):
    user = user or frappe.session.user
    return bool(set(frappe.get_roles(user)).intersection(set(get_approval_roles())))


def upsert_default_print_format(doctype, print_format):
    if not frappe.db.exists("Print Format", {"name": print_format, "doc_type": doctype}):
        return

    filters = {
        "doctype_or_field": "DocType",
        "doc_type": doctype,
        "property": "default_print_format",
    }
    if frappe.db.exists("Property Setter", filters):
        frappe.db.set_value("Property Setter", filters, "value", print_format)
    else:
        frappe.get_doc(
            {
                "doctype": "Property Setter",
                "doctype_or_field": "DocType",
                "doc_type": doctype,
                "property": "default_print_format",
                "property_type": "Data",
                "value": print_format,
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache(doctype=doctype)


def cleanup_legacy_memo_artifacts():
    property_setter_names = [
        "Memo-naming_series-default",
        "Memo-naming_series-options",
    ]
    for setter_name in property_setter_names:
        if frappe.db.exists("Property Setter", setter_name):
            frappe.delete_doc("Property Setter", setter_name, ignore_permissions=True, force=True)

    if frappe.db.exists("Print Format", "Memo View"):
        frappe.delete_doc("Print Format", "Memo View", ignore_permissions=True, force=True)
