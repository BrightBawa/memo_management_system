from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMemo(FrappeTestCase):
    def test_requires_to_recipient(self):
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "subject": "Test Memo",
                "content": "<p>Hello</p>",
                "recipients": [{"recipient_type": "Cc", "employee": "EMP-0001"}],
            }
        )

        with patch(
            "memo_management_system.memo_management_system.doctype.memo.memo.frappe.db.exists",
            return_value=True,
        ):
            self.assertRaises(frappe.ValidationError, memo.validate)

    def test_detects_duplicate_reference_rows(self):
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "subject": "Test Memo",
                "content": "<p>Hello</p>",
                "recipients": [{"recipient_type": "To", "employee": "EMP-0001"}],
                "reference_documents": [
                    {
                        "relation_type": "General Reference",
                        "reference_doctype": "Purchase Order",
                        "reference_name": "PO-0001",
                    },
                    {
                        "relation_type": "Supporting Document",
                        "reference_doctype": "Purchase Order",
                        "reference_name": "PO-0001",
                    },
                ],
            }
        )

        def fake_exists(doctype, name=None):
            if doctype == "Employee":
                return True
            return True

        with patch(
            "memo_management_system.memo_management_system.doctype.memo.memo.frappe.db.exists",
            side_effect=fake_exists,
        ):
            self.assertRaises(frappe.ValidationError, memo.validate)

    def test_rejects_action_point_due_date_before_memo_date(self):
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "memo_date": "2026-07-10",
                "subject": "Execution Memo",
                "content": "<p>Hello</p>",
                "recipients": [{"recipient_type": "To", "employee": "EMP-0001"}],
                "action_points": [
                    {
                        "action_title": "Complete filing",
                        "assigned_employee": "EMP-0002",
                        "due_date": "2026-07-09",
                    }
                ],
            }
        )

        with patch(
            "memo_management_system.memo_management_system.doctype.memo.memo.frappe.db.exists",
            return_value=True,
        ):
            self.assertRaises(frappe.ValidationError, memo.validate)
