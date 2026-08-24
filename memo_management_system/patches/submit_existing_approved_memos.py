import frappe


def execute():
    """Align approved legacy memos with Memo's native submission lifecycle."""
    memo_names = frappe.get_all(
        "Memo",
        filters={"status": "Approved", "docstatus": 0},
        pluck="name",
    )
    if not memo_names:
        return

    # The approval/circulation side effects already ran when these records
    # became Approved. Only normalize Frappe's document status; replaying a
    # submit would duplicate routing entries and notifications.
    frappe.db.set_value(
        "Memo",
        {"name": ("in", memo_names)},
        "docstatus",
        1,
        update_modified=False,
    )

    for table_field in frappe.get_meta("Memo").get_table_fields():
        frappe.db.set_value(
            table_field.options,
            {"parenttype": "Memo", "parent": ("in", memo_names)},
            "docstatus",
            1,
            update_modified=False,
        )
