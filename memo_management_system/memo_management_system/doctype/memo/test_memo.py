from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMemo(FrappeTestCase):
    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.has_global_access",
        return_value=False,
    )
    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.has_approval_access",
        return_value=False,
    )
    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.get_memo_settings"
    )
    def test_ordinary_user_cannot_disable_required_approval(
        self, get_settings, _approval_access, _global_access
    ):
        get_settings.return_value = frappe._dict({"require_approval_by_default": 1})
        memo = frappe.get_doc({"doctype": "Memo", "requires_approval": 0})

        self.assertRaises(
            frappe.PermissionError, memo._validate_approval_requirement
        )

    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.has_approval_access",
        return_value=True,
    )
    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.get_memo_settings"
    )
    def test_authorized_approver_can_disable_required_approval(
        self, get_settings, _approval_access
    ):
        get_settings.return_value = frappe._dict({"require_approval_by_default": 1})
        memo = frappe.get_doc({"doctype": "Memo", "requires_approval": 0})

        memo._validate_approval_requirement()

    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.frappe.db.get_value",
        return_value="Pending Approval",
    )
    def test_workflow_system_write_skips_second_approval_content_check(self, _get_value):
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "name": "MEMO-TEST-APPROVAL",
                "status": "Approved",
                "approver": "approver@example.com",
            }
        )
        memo.flags.memo_system_write = True

        with patch(
            "memo_management_system.memo_management_system.doctype.memo.memo.frappe.get_doc"
        ) as get_doc:
            memo.before_save()

        get_doc.assert_not_called()

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

    @patch("memo_management_system.api.permissions.has_approval_access", return_value=False)
    @patch("memo_management_system.api.permissions.has_global_access", return_value=False)
    def test_secondary_approver_has_same_pending_memo_access(self, _global_access, _approval_access):
        from memo_management_system.api.permissions import has_memo_permission

        memo = frappe._dict(
            {
                "owner": "author@example.com",
                "approver": "primary@example.com",
                "secondary_approver": "secondary@example.com",
                "status": "Pending Approval",
                "confidentiality": "Internal",
                "recipients": [],
            }
        )
        self.assertTrue(
            has_memo_permission(
                memo, user="secondary@example.com", permission_type="read"
            )
        )
        self.assertTrue(
            has_memo_permission(
                memo, user="secondary@example.com", permission_type="write"
            )
        )

    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.has_approval_access",
        return_value=False,
    )
    @patch(
        "memo_management_system.memo_management_system.doctype.memo.memo.has_global_access",
        return_value=False,
    )
    def test_secondary_approver_can_decide_memo(self, _global_access, _approval_access):
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "approver": "primary@example.com",
                "secondary_approver": "secondary@example.com",
            }
        )
        self.assertTrue(memo.can_current_user_approve("secondary@example.com"))

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

    def test_rejects_empty_memo_attachment_row(self):
        memo = frappe.get_doc(
            {
                "doctype": "Memo",
                "subject": "Test Memo",
                "content": "<p>Hello</p>",
                "recipients": [{"recipient_type": "To", "user_id": "recipient@example.com"}],
                "memo_attachments": [{"description": "Missing upload"}],
            }
        )

        with patch(
            "memo_management_system.memo_management_system.doctype.memo.memo.frappe.db.exists",
            return_value=True,
        ):
            self.assertRaises(frappe.ValidationError, memo.validate)

    def test_memo_attachments_are_part_of_amendment_hash(self):
        first = frappe.get_doc(
            {
                "doctype": "Memo",
                "memo_attachments": [
                    {"description": "Budget", "attachment": "/files/budget.pdf"}
                ],
            }
        )
        second = frappe.get_doc(
            {
                "doctype": "Memo",
                "memo_attachments": [
                    {"description": "Minutes", "attachment": "/files/minutes.pdf"}
                ],
            }
        )

        self.assertNotEqual(first._amendment_hash(), second._amendment_hash())

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
