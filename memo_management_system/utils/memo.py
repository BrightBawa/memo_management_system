import frappe


MEMO_USER_ROLE = "Memo User"
MEMO_APPROVER_ROLE = "Memo Approver"
MEMO_MANAGER_ROLE = "Memo Manager"
MEMO_ADMIN_ROLE = "Memo Administrator"
LEGACY_WORKFLOW_NAME = "Memo Approval Workflow"
MEMO_WORKFLOW_TASKS_NAME = "Memo Workflow Side Effects"
MEMO_WORKFLOW_METHOD = "Process Memo Workflow Transition"

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


def setup_memo_workflow():
    """Install the standard Workflow which owns Memo state transitions.

    Memo-specific circulation and audit behaviour is attached as a synchronous
    Workflow Transition Task, so the state change and its side effects share a
    transaction.
    """
    ensure_roles()
    for state in ("Draft", "Pending Approval", "Approved", "Rejected", "Amended"):
        if not frappe.db.exists("Workflow State", state):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
                ignore_permissions=True
            )

    for action in ("Submit for Approval", "Approve and Circulate", "Approve Memo", "Reject Memo", "Amend Memo"):
        if not frappe.db.exists("Workflow Action Master", action):
            frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
                ignore_permissions=True
            )

    if frappe.db.exists("Workflow Transition Tasks", MEMO_WORKFLOW_TASKS_NAME):
        task = frappe.get_doc("Workflow Transition Tasks", MEMO_WORKFLOW_TASKS_NAME)
        task.set("tasks", [{"task": MEMO_WORKFLOW_METHOD, "enabled": 1, "asynchronous": 0}])
        task.flags.ignore_version = True
        task.save(ignore_permissions=True)
    else:
        task = frappe.get_doc({
            "doctype": "Workflow Transition Tasks",
            "name": MEMO_WORKFLOW_TASKS_NAME,
            "tasks": [{"task": MEMO_WORKFLOW_METHOD, "enabled": 1, "asynchronous": 0}],
        })
        task.insert(ignore_permissions=True)

    owner_condition = "doc.owner == frappe.session.user"
    selected_approver_condition = "doc.approver == frappe.session.user"
    transitions = [
        _memo_transition("Draft", "Submit for Approval", "Pending Approval", MEMO_USER_ROLE,
            f"doc.requires_approval and ({owner_condition})"),
        _memo_transition("Rejected", "Amend Memo", "Amended", MEMO_USER_ROLE,
            owner_condition),
        _memo_transition("Amended", "Submit for Approval", "Pending Approval", MEMO_USER_ROLE,
            f"doc.requires_approval and ({owner_condition})"),
        _memo_transition("Draft", "Approve and Circulate", "Approved", MEMO_USER_ROLE,
            f"not doc.requires_approval and ({owner_condition})"),
        _memo_transition("Amended", "Approve and Circulate", "Approved", MEMO_USER_ROLE,
            f"not doc.requires_approval and ({owner_condition})"),
        _memo_transition("Pending Approval", "Approve Memo", "Approved", "All",
            selected_approver_condition),
        _memo_transition("Pending Approval", "Reject Memo", "Rejected", "All",
            selected_approver_condition),
    ]

    # Configured approval roles retain their authority to decide any pending
    # memo. The condition avoids duplicate buttons when the user is also the
    # specifically selected approver.
    settings = get_memo_settings()
    approval_roles = list(dict.fromkeys(row.role for row in settings.approval_roles if row.role))
    global_roles = list(dict.fromkeys(row.role for row in settings.global_access_roles if row.role))
    for role in global_roles:
        transitions.extend([
            _memo_transition("Draft", "Submit for Approval", "Pending Approval", role,
                "doc.requires_approval and doc.owner != frappe.session.user"),
            _memo_transition("Rejected", "Amend Memo", "Amended", role,
                "doc.owner != frappe.session.user"),
            _memo_transition("Amended", "Submit for Approval", "Pending Approval", role,
                "doc.requires_approval and doc.owner != frappe.session.user"),
            _memo_transition("Draft", "Approve and Circulate", "Approved", role,
                "not doc.requires_approval and doc.owner != frappe.session.user"),
            _memo_transition("Amended", "Approve and Circulate", "Approved", role,
                "not doc.requires_approval and doc.owner != frappe.session.user"),
        ])
    for role in approval_roles:
        transitions.extend([
            _memo_transition("Pending Approval", "Approve Memo", "Approved", role,
                "doc.approver != frappe.session.user"),
            _memo_transition("Pending Approval", "Reject Memo", "Rejected", role,
                "doc.approver != frappe.session.user"),
        ])

    workflow_values = {
        "document_type": "Memo",
        "workflow_state_field": "status",
        "is_active": 1,
        "override_status": 1,
        "send_email_alert": 0,
        "enable_action_confirmation": 1,
        "states": [
            {"state": "Draft", "doc_status": "0", "allow_edit": MEMO_USER_ROLE},
            # Every authenticated user has All. The transition condition,
            # document share, and controller restrict decisions to the user
            # specifically selected on this memo.
            {"state": "Pending Approval", "doc_status": "0", "allow_edit": "All"},
            {"state": "Approved", "doc_status": "0", "allow_edit": MEMO_MANAGER_ROLE},
            # Memo.before_save prevents direct edits in Rejected; Memo User is
            # required here so the owner can execute the Amend Memo action.
            {"state": "Rejected", "doc_status": "0", "allow_edit": MEMO_USER_ROLE},
            {"state": "Amended", "doc_status": "0", "allow_edit": MEMO_USER_ROLE},
        ],
        "transitions": transitions,
    }
    if frappe.db.exists("Workflow", LEGACY_WORKFLOW_NAME):
        workflow = frappe.get_doc("Workflow", LEGACY_WORKFLOW_NAME)
        workflow.update(workflow_values)
        workflow.set("states", workflow_values["states"])
        workflow.set("transitions", workflow_values["transitions"])
        workflow.flags.ignore_version = True
        workflow.flags.ignore_validate_update_after_submit = True
        workflow.save(ignore_permissions=True)
    else:
        workflow = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": LEGACY_WORKFLOW_NAME,
            **workflow_values,
        })
        workflow.insert(ignore_permissions=True)
    frappe.clear_cache(doctype="Memo")


def _memo_transition(state, action, next_state, allowed, condition):
    return {
        "state": state,
        "action": action,
        "next_state": next_state,
        "allowed": allowed,
        "allow_self_approval": 1,
        "condition": condition,
        "transition_tasks": MEMO_WORKFLOW_TASKS_NAME,
    }


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
