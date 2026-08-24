import frappe


def execute():
    for memo in frappe.get_all(
        "Memo",
        fields=["name", "approver", "secondary_approver"],
        limit_page_length=0,
    ):
        values = {}
        for user_field, employee_field, designation_field in (
            ("approver", "approver_employee", "approver_designation"),
            ("secondary_approver", "secondary_approver_employee", "secondary_approver_designation"),
        ):
            user = memo.get(user_field)
            employee = frappe.db.get_value(
                "Employee",
                {"user_id": user, "status": "Active"},
                ["name", "designation"],
                as_dict=True,
            ) if user else None
            values[employee_field] = employee.name if employee else None
            values[designation_field] = employee.designation if employee else None

        frappe.db.set_value("Memo", memo.name, values, update_modified=False)
