import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from memo_management_system.utils.memo import (
    MEMO_USER_ROLE,
    ensure_roles,
    sync_memo_roles_for_existing_employees,
)


class MemoSettings(Document):
    def validate(self):
        ensure_roles()
        self.memo_user_role = self.memo_user_role or MEMO_USER_ROLE
        self.default_acknowledgement_window_days = cint(self.default_acknowledgement_window_days or 0) or 3
        if self.default_acknowledgement_window_days < 1:
            frappe.throw(_("Default acknowledgement window must be at least 1 day."))
        self._deduplicate_roles("global_access_roles")
        self._deduplicate_roles("approval_roles")

    def _deduplicate_roles(self, fieldname):
        seen = set()
        unique_rows = []
        for row in self.get(fieldname) or []:
            if not row.role or row.role in seen:
                continue
            seen.add(row.role)
            unique_rows.append({"role": row.role})

        self.set(fieldname, unique_rows)


@frappe.whitelist()
def sync_employee_roles():
    if not frappe.has_permission("Memo Settings", "write"):
        frappe.throw(_("You do not have permission to sync memo roles."), frappe.PermissionError)

    ensure_roles()
    sync_memo_roles_for_existing_employees()
    frappe.clear_cache()
    return {"status": "ok"}
