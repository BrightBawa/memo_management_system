import frappe

from memo_management_system.utils.memo import LEGACY_WORKFLOW_NAME


def execute():
    """Restore the app-managed Workflow to an editable draft record.

    Some older installations retained the Workflow with docstatus 1 even
    though Workflow is no longer a submittable DocType. That makes the Desk
    form read-only and forces app setup to bypass update-after-submit checks.
    """
    if not frappe.db.exists("Workflow", LEGACY_WORKFLOW_NAME):
        return

    values = {"docstatus": 0}
    if not frappe.db.get_value("Workflow", LEGACY_WORKFLOW_NAME, "owner"):
        values["owner"] = "Administrator"

    frappe.db.set_value(
        "Workflow",
        LEGACY_WORKFLOW_NAME,
        values,
        update_modified=False,
    )
