import frappe


def execute():
    """Move legacy single attachments into the multiple-attachment child table."""
    for memo_name in frappe.get_all(
        "Memo",
        filters={"primary_attachment": ["is", "set"]},
        pluck="name",
        limit_page_length=0,
    ):
        primary_attachment = frappe.db.get_value("Memo", memo_name, "primary_attachment")
        existing_rows = frappe.get_all(
            "Memo Attachments",
            filters={"parent": memo_name, "parenttype": "Memo"},
            fields=["attachment", "idx"],
            order_by="idx asc",
        )
        if any(row.attachment == primary_attachment for row in existing_rows):
            continue

        child = frappe.get_doc(
            {
                "doctype": "Memo Attachments",
                "parent": memo_name,
                "parenttype": "Memo",
                "parentfield": "memo_attachments",
                "idx": max((row.idx for row in existing_rows), default=0) + 1,
                "attachment": primary_attachment,
                "description": "Primary Attachment",
            }
        )
        # A direct child insert avoids firing unrelated Memo update hooks while
        # preserving the submitted parent document and its audit timestamps.
        child.db_insert()
