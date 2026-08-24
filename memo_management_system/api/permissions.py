import frappe

from memo_management_system.utils.memo import (
    DEFAULT_DESK_ROLES,
    MEMO_ADMIN_ROLE,
    MEMO_MANAGER_ROLE,
    has_approval_access,
    has_global_access,
    is_employee_scope_enforced,
)


def get_memo_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if user == "Administrator" or _has_role(user, MEMO_MANAGER_ROLE):
        return ""

    user_value = frappe.db.escape(user)
    recipient_clause = (
        " or exists ("
        "select 1 from `tabMemo recipient` recipient "
        "where recipient.parent = `tabMemo`.name "
        "and recipient.parenttype = 'Memo' "
        f"and recipient.user_id = {user_value}"
        ")"
    )

    participant_condition = (
        f"(`tabMemo`.`owner` = {user_value} "
        f"or `tabMemo`.`approver` = {user_value} "
        f"or `tabMemo`.`secondary_approver` = {user_value} "
        f"{recipient_clause})"
    )

    # Standard users remain limited to memos in which they participate.
    if not (has_global_access(user) or has_approval_access(user)):
        if is_employee_scope_enforced():
            return participant_condition
        return (
            "(coalesce(`tabMemo`.`confidentiality`, 'Internal') = 'Internal' "
            f"or {participant_condition})"
        )

    # Privileged roles may see all Internal memos. Memo Administrators may
    # additionally see all Confidential memos. Restricted memos remain
    # participant-only unless the user is a Memo Manager.
    classifications = ["'Internal'"]
    if _has_role(user, MEMO_ADMIN_ROLE):
        classifications.append("'Confidential'")
    return (
        f"(coalesce(`tabMemo`.`confidentiality`, 'Internal') in ({', '.join(classifications)}) "
        f"or {participant_condition})"
    )


def has_memo_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    permission_type = permission_type or "read"

    if permission_type == "create":
        return _user_has_memo_role(user)

    if not doc:
        return False

    confidentiality = doc.confidentiality or "Internal"
    participant = _can_access_memo(doc, user)
    is_manager = _has_role(user, MEMO_MANAGER_ROLE)
    is_memo_admin = _has_role(user, MEMO_ADMIN_ROLE)

    if confidentiality == "Restricted" and permission_type in {"email", "export"}:
        return False

    if user == "Administrator":
        return True

    if permission_type in {"read", "print", "email", "share"}:
        if confidentiality == "Restricted":
            return is_manager or participant
        if confidentiality == "Confidential":
            return is_manager or is_memo_admin or participant
        if has_global_access(user):
            return True
        # Approval roles are configured as users who may approve *any* memo;
        # they must therefore be able to open the pending memo first.
        if has_approval_access(user):
            return True
        if not is_employee_scope_enforced():
            return _user_has_memo_role(user)
        return _can_access_memo(doc, user)

    if permission_type == "write":
        # Workflow actions require write permission before their transition
        # conditions and controller checks are evaluated.
        if doc.status == "Pending Approval":
            return (
                user in {doc.approver, doc.secondary_approver}
                or has_approval_access(user)
                or has_global_access(user)
            )

        # Rejected needs write permission only so Frappe can execute the
        # Rejected -> Amended workflow transition. Memo.before_save still
        # blocks direct changes while the stored state is Rejected.
        return (doc.owner == user or has_global_access(user)) and doc.status in {
            "Draft", "Rejected", "Amended"
        }

    if permission_type == "delete":
        return doc.owner == user and doc.status == "Draft"

    return False


def _has_role(user, role):
    return role in frappe.get_roles(user)


def _can_access_memo(doc, user):
    if doc.owner == user or user in {doc.approver, doc.secondary_approver}:
        return True

    return any(row.user_id == user for row in doc.recipients or [])


def _user_has_memo_role(user):
    roles = set(frappe.get_roles(user))
    return bool(roles.intersection(DEFAULT_DESK_ROLES))
