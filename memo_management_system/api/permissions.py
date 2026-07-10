import frappe

from memo_management_system.utils.memo import (
    DEFAULT_DESK_ROLES,
    get_employee_for_user,
    has_approval_access,
    has_global_access,
    is_employee_scope_enforced,
)


def get_memo_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if user == "Administrator" or has_global_access(user) or has_approval_access(user):
        return ""

    if not is_employee_scope_enforced():
        return ""

    employee = get_employee_for_user(user)
    if not employee:
        return "1=0"

    user_value = frappe.db.escape(user)
    employee_value = frappe.db.escape(employee)
    return (
        f"(`tabMemo`.`owner` = {user_value} "
        f"or `tabMemo`.`approver` = {user_value} "
        "or exists ("
        "select 1 from `tabMemo recipient` recipient "
        "where recipient.parent = `tabMemo`.name "
        "and recipient.parenttype = 'Memo' "
        f"and recipient.employee = {employee_value}"
        "))"
    )


def has_memo_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    permission_type = permission_type or "read"

    if permission_type == "create":
        return _user_has_memo_role(user)

    if not doc:
        return False

    if user == "Administrator" or has_global_access(user):
        return True

    if permission_type in {"read", "print", "email", "share"}:
        if not is_employee_scope_enforced():
            return _user_has_memo_role(user)
        return _can_access_memo(doc, user)

    if permission_type == "write":
        return doc.owner == user and doc.status in {"Draft", "Rejected"}

    if permission_type == "delete":
        return doc.owner == user and doc.status == "Draft"

    return False


def _can_access_memo(doc, user):
    employee = get_employee_for_user(user)
    if doc.owner == user or doc.approver == user:
        return True

    if not employee:
        return False

    return any(row.employee == employee for row in doc.recipients or [])


def _user_has_memo_role(user):
    roles = set(frappe.get_roles(user))
    return bool(roles.intersection(DEFAULT_DESK_ROLES))
