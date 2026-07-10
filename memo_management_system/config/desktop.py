from frappe import _


def get_data():
    return [
        {
            "module_name": "Memo Management System",
            "category": "Modules",
            "label": _("Memo Management"),
            "color": "blue",
            "icon": "octicon octicon-mail",
            "type": "module",
            "description": _("Internal memo drafting, routing, and recipient tracking."),
        }
    ]
