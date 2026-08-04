from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMemo(FrappeTestCase):
    @patch("memo_management_system.api.permissions.frappe.get_roles")
    def test_restricted_memo_blocks_export_and_email_for_manager(self, get_roles):
        from memo_management_system.api.permissions import has_memo_permission

        get_roles.return_value = ["Memo Manager"]
        memo = frappe._dict(
            {
                "owner": "author@example.com",
                "approver": "approver@example.com",
                "confidentiality": "Restricted",
                "recipients": [],
            }
        )
        self.assertTrue(has_memo_permission(memo, user="manager@example.com", permission_type="read"))
        self.assertFalse(has_memo_permission(memo, user="manager@example.com", permission_type="email"))
        self.assertFalse(has_memo_permission(memo, user="manager@example.com", permission_type="export"))

    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.frappe.db.get_value"
    )
    def test_existing_origin_is_not_replaced_by_later_actor(self, get_value):
        get_value.return_value = frappe._dict(
            {
                "name": "EMP-APPROVER",
                "employee_name": "Later Approver",
                "designation": "Approver",
                "department": "Another Department",
                "company": "Another Company",
                "reports_to": None,
            }
        )
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "name": "MEMO-TEST-ORIGIN",
                "prepared_by": "creator@example.com",
                "origin_employee": "EMP-CREATOR",
                "originator_name": "Original Creator",
                "originator_designation": "Officer",
                "department": "Creator Department",
                "company": "GCIHS",
            }
        )

        memo._set_origin_details()

        self.assertEqual(memo.origin_employee, "EMP-CREATOR")
        self.assertEqual(memo.originator_name, "Original Creator")
        self.assertEqual(memo.department, "Creator Department")

    @patch("memo_management_system.api.permissions.has_approval_access", return_value=True)
    @patch("memo_management_system.api.permissions.has_global_access", return_value=False)
    def test_configured_approver_can_read_any_memo(self, _global_access, _approval_access):
        from memo_management_system.api.permissions import has_memo_permission

        memo = frappe._dict({"owner": "author@example.com", "recipients": []})
        self.assertTrue(
            has_memo_permission(
                memo, user="approver@example.com", permission_type="read"
            )
        )

    @patch("memo_management_system.api.permissions.has_approval_access", return_value=False)
    @patch("memo_management_system.api.permissions.has_global_access", return_value=False)
    def test_selected_approver_can_write_pending_memo(self, _global_access, _approval_access):
        from memo_management_system.api.permissions import has_memo_permission

        memo = frappe._dict(
            {
                "owner": "author@example.com",
                "approver": "approver@example.com",
                "status": "Pending Approval",
                "confidentiality": "Internal",
                "recipients": [],
            }
        )
        self.assertTrue(
            has_memo_permission(memo, user="approver@example.com", permission_type="write")
        )
        self.assertFalse(
            has_memo_permission(memo, user="other@example.com", permission_type="write")
        )

    def test_requires_to_recipient(self):
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "subject": "Test Memo",
                "content": "<p>Hello</p>",
                "recipients": [{"recipient_type": "Cc", "user_id": "recipient@example.com"}],
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
                "recipients": [{"recipient_type": "To", "user_id": "recipient@example.com"}],
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
                "recipients": [{"recipient_type": "To", "user_id": "recipient@example.com"}],
                "action_points": [
                    {
                        "action_title": "Complete filing",
                        "assigned_user": "assignee@example.com",
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

    def test_action_points_cannot_start_before_approval(self):
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "status": "Pending Approval",
                "action_points": [{"name": "ACTION-1"}],
            }
        )

        self.assertRaises(
            frappe.ValidationError,
            memo.update_action_point_status_action,
            "ACTION-1",
            "In Progress",
        )
