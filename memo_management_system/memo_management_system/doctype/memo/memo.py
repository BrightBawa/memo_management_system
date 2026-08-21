import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    add_days,
    cint,
    cstr,
    format_datetime,
    formatdate,
    get_fullname,
    get_url_to_form,
    now_datetime,
    nowdate,
)
from frappe.utils.html_utils import clean_html

from memo_management_system.utils.memo import (
    get_employee_for_user,
    get_memo_settings,
    has_approval_access,
    has_global_access,
)

MEMO_STATUSES = {"Draft", "Pending Approval", "Approved", "Rejected", "Amended", "Cancelled"}
ACTION_POINT_STATUSES = {"Open", "In Progress", "Completed", "Cancelled"}
EDITABLE_STATUSES = {"Draft", "Amended"}


class Memo(Document):
    def after_insert(self):
        self._sync_participant_shares()

    def on_update(self):
        self._sync_participant_shares()

    def before_validate(self):
        self._set_defaults()
        self._set_origin_details()
        self._set_recipient_details()
        self._set_action_point_details()
        self._set_default_approver()

    def validate(self):
        self.subject = cstr(self.subject).strip()
        self.summary = cstr(self.summary).strip()
        self.approval_remarks = cstr(self.approval_remarks).strip()

        if self.content:
            self.content = clean_html(self.content)

        if not self.subject:
            frappe.throw(_("Subject is required."))
        if not self.content:
            frappe.throw(_("Memo content is required."))
        if self.status not in MEMO_STATUSES:
            frappe.throw(_("Invalid memo status."))
        if self.effective_date and self.memo_date and self.effective_date < self.memo_date:
            frappe.throw(_("Effective date cannot be earlier than the memo date."))
        if (
            self.require_recipient_acknowledgement
            and self.acknowledgement_due_date
            and self.memo_date
            and self.acknowledgement_due_date < self.memo_date
        ):
            frappe.throw(_("Acknowledgement due date cannot be earlier than the memo date."))

        self._validate_recipients()
        self._validate_links()
        self._validate_action_points()

    def before_save(self):
        if self.is_new():
            return

        previous_status = frappe.db.get_value("Memo", self.name, "status")
        if previous_status in EDITABLE_STATUSES:
            if previous_status == "Amended" and self._has_meaningful_amendment():
                self.amended_by = frappe.session.user
                self.amended_on = now_datetime()
            return

        # Workflow side effects validate the browser-supplied business content
        # before setting this flag.  Honour the flag before re-running the
        # pending-approval comparison: validation for the destination state can
        # legitimately update recipient acknowledgement/circulation fields.
        if getattr(self.flags, "memo_system_write", False):
            return

        if previous_status == "Pending Approval" and self.can_current_user_approve():
            stored = frappe.get_doc("Memo", self.name)
            if stored._amendment_hash(exclude_tables={"action_points"}) != self._amendment_hash(
                exclude_tables={"action_points"}
            ):
                frappe.throw(_("Approvers may only change Execution and Follow-up while approval is pending."))
            return

        frappe.throw(_("Only draft or amended memos can be edited."))

    def _amendment_hash(self, exclude_tables=None):
        """Fingerprint business content while excluding workflow/audit metadata."""
        exclude_tables = set(exclude_tables or [])
        fields = (
            "memo_category", "priority", "confidentiality", "requires_approval", "approver",
            "company", "department", "memo_date", "effective_date", "origin_employee",
            "originator_name", "originator_designation", "subject", "summary", "content",
            "require_recipient_acknowledgement", "acknowledgement_due_date", "material_request",
            "purchase_order", "primary_attachment",
        )
        payload = {field: self.get(field) for field in fields}
        for table in ("recipients", "action_points", "reference_documents"):
            if table in exclude_tables:
                continue
            payload[table] = [
                {key: value for key, value in row.as_dict().items() if key not in {
                    "name", "owner", "creation", "modified", "modified_by", "docstatus",
                    "idx", "parent", "parentfield", "parenttype", "doctype",
                }}
                for row in (self.get(table) or [])
            ]
        serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _has_meaningful_amendment(self):
        return bool(self.rejection_snapshot_hash) and self._amendment_hash() != self.rejection_snapshot_hash

    def _set_defaults(self):
        settings = get_memo_settings()
        self.naming_series = self.naming_series or settings.default_naming_series
        self.memo_date = self.memo_date or nowdate()
        self.status = self.status or "Draft"
        self.confidentiality = self.confidentiality or settings.default_confidentiality
        self.priority = self.priority or settings.default_priority
        self.prepared_by = self.prepared_by or self.owner or frappe.session.user
        self.prepared_on = self.prepared_on or now_datetime()

        if self.requires_approval is None:
            self.requires_approval = settings.require_approval_by_default
        if self.require_recipient_acknowledgement is None:
            self.require_recipient_acknowledgement = settings.require_acknowledgement_by_default

        if self.require_recipient_acknowledgement and not self.acknowledgement_due_date:
            self.acknowledgement_due_date = add_days(
                self.memo_date, cint(settings.default_acknowledgement_window_days) or 3
            )
        elif not self.require_recipient_acknowledgement:
            self.acknowledgement_due_date = None

    def _set_origin_details(self):
        # Origin is a snapshot of the memo creator, not the user who later
        # approves, acknowledges, re-circulates, or updates an action point.
        origin_user = self.prepared_by or self.owner or frappe.session.user
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": origin_user},
            ["name", "employee_name", "designation", "department", "company", "reports_to"],
            as_dict=True,
        )

        if employee:
            if self.is_new():
                self.origin_employee = employee.name
                self.originator_name = employee.employee_name
                self.originator_designation = employee.designation
                self.department = employee.department
                self.company = employee.company
            else:
                # Preserve the historical origin snapshot on existing memos,
                # while repairing any legacy blank values.
                self.origin_employee = self.origin_employee or employee.name
                self.originator_name = self.originator_name or employee.employee_name
                self.originator_designation = self.originator_designation or employee.designation
                self.department = self.department or employee.department
                self.company = self.company or employee.company
            self._reports_to = employee.reports_to
        else:
            self.originator_name = self.originator_name or (get_fullname(origin_user) or origin_user)

    def _set_recipient_details(self):
        for row in self.recipients or []:
            if row.requires_acknowledgement in (None, ""):
                row.requires_acknowledgement = 1 if self.require_recipient_acknowledgement else 0

            if not row.user_id and row.employee:
                row.user_id = frappe.db.get_value("Employee", row.employee, "user_id")

            employee_name = None
            if row.user_id:
                employee_name = frappe.db.get_value(
                    "Employee", {"user_id": row.user_id, "status": "Active"}, "name"
                )
                row.employee = employee_name

            if employee_name:
                employee = frappe.db.get_value(
                    "Employee",
                    employee_name,
                    [
                        "employee_name",
                        "user_id",
                        "designation",
                        "department",
                        "company_email",
                        "prefered_email",
                        "personal_email",
                    ],
                    as_dict=True,
                )
                if employee:
                    row.employee_name = employee.employee_name
                    row.user_id = employee.user_id
                    row.designation = employee.designation
                    row.department = employee.department
                    row.official_mail = (
                        employee.company_email or employee.prefered_email or employee.personal_email or ""
                    )
            elif row.user_id:
                row.employee_name = get_fullname(row.user_id) or row.user_id
                row.designation = None
                row.department = None
                row.official_mail = row.user_id

            if row.requires_acknowledgement:
                row.acknowledgement_due_date = row.acknowledgement_due_date or self.acknowledgement_due_date
                row.acknowledgement_status = self._default_acknowledgement_status(row)
            else:
                row.acknowledgement_due_date = None
                row.acknowledgement_status = "Not Required"
                row.acknowledged_by = None
                row.acknowledged_on = None

    def _set_action_point_details(self):
        for row in self.action_points or []:
            row.action_title = cstr(row.action_title).strip()
            row.action_details = cstr(row.action_details).strip()
            row.completion_notes = cstr(row.completion_notes).strip()
            row.priority = row.priority or self.priority or "Normal"
            row.status = row.status or "Open"

            if not row.assigned_user and row.assigned_employee:
                row.assigned_user = frappe.db.get_value("Employee", row.assigned_employee, "user_id")

            if row.assigned_user:
                employee = frappe.db.get_value(
                    "Employee", {"user_id": row.assigned_user, "status": "Active"},
                    ["name", "employee_name", "designation"], as_dict=True,
                )
                row.assigned_employee = employee.name if employee else None
                row.assigned_employee_name = employee.employee_name if employee else (get_fullname(row.assigned_user) or row.assigned_user)
                row.assigned_designation = employee.designation if employee else None

            if row.status == "Completed":
                row.completed_by = row.completed_by or frappe.session.user
                row.completed_on = row.completed_on or now_datetime()
            elif row.status != "Cancelled":
                row.completed_by = None
                row.completed_on = None

    def _set_default_approver(self):
        if not self.requires_approval or self.approver:
            return

        reports_to = getattr(self, "_reports_to", None)
        if not reports_to and self.origin_employee:
            reports_to = frappe.db.get_value("Employee", self.origin_employee, "reports_to")
        if not reports_to:
            return

        approver_user = frappe.db.get_value("Employee", reports_to, "user_id")
        if approver_user:
            self.approver = approver_user

    def _default_acknowledgement_status(self, row):
        if not row.requires_acknowledgement:
            return "Not Required"
        if row.acknowledged_on or row.acknowledgement_status == "Acknowledged":
            return "Acknowledged"
        if self.status == "Approved":
            return "Pending"
        return "Pending Circulation"

    def _clear_circulation_state(self):
        self.circulated_by = None
        self.circulated_on = None
        for row in self.recipients or []:
            if row.requires_acknowledgement and row.acknowledgement_status != "Acknowledged":
                row.acknowledgement_status = "Pending Circulation"
            elif not row.requires_acknowledgement:
                row.acknowledgement_status = "Not Required"

    def _mark_ready_for_circulation(self, actor=None):
        self.circulated_by = actor or frappe.session.user
        self.circulated_on = now_datetime()

        for row in self.recipients or []:
            if row.requires_acknowledgement:
                row.acknowledgement_due_date = row.acknowledgement_due_date or self.acknowledgement_due_date
                if row.acknowledgement_status != "Acknowledged":
                    row.acknowledgement_status = "Pending"
            else:
                row.acknowledgement_status = "Not Required"

    def _validate_recipients(self):
        if not self.recipients:
            frappe.throw(_("Add at least one recipient before saving the memo."))

        seen = set()
        has_to_recipient = False

        for row in self.recipients:
            row.recipient_type = row.recipient_type or "To"
            user = cstr(row.user_id).strip()
            if not user:
                frappe.throw(_("Each recipient row must have a user."))
            if not frappe.db.exists("User", {"name": user, "enabled": 1, "user_type": "System User"}):
                frappe.throw(_("Recipient user {0} is not an enabled System User.").format(user))

            if row.recipient_type == "To":
                has_to_recipient = True

            if user in seen:
                frappe.throw(_("Duplicate recipient detected for user {0}.").format(user))
            seen.add(user)

            if row.requires_acknowledgement and not row.acknowledgement_due_date:
                row.acknowledgement_due_date = self.acknowledgement_due_date

            if (
                row.requires_acknowledgement
                and row.acknowledgement_due_date
                and self.memo_date
                and row.acknowledgement_due_date < self.memo_date
            ):
                frappe.throw(
                    _("Acknowledgement due date for user {0} cannot be earlier than the memo date.").format(
                        user
                    )
                )

        if not has_to_recipient:
            frappe.throw(_("Add at least one primary recipient of type To."))

    def _validate_links(self):
        if self.material_request and not frappe.db.exists("Material Request", self.material_request):
            frappe.throw(_("Material Request {0} does not exist.").format(self.material_request))

        if self.purchase_order and not frappe.db.exists("Purchase Order", self.purchase_order):
            frappe.throw(_("Purchase Order {0} does not exist.").format(self.purchase_order))

        seen = set()
        for row in self.reference_documents or []:
            if not row.reference_doctype or not row.reference_name:
                frappe.throw(_("Each related document row must include both DocType and document name."))
            if not frappe.db.exists(row.reference_doctype, row.reference_name):
                frappe.throw(
                    _("Related document {0} {1} does not exist.").format(
                        row.reference_doctype, row.reference_name
                    )
                )
            key = (row.reference_doctype, row.reference_name)
            if key in seen:
                frappe.throw(
                    _("Duplicate related document row detected for {0} {1}.").format(
                        row.reference_doctype, row.reference_name
                    )
                )
            seen.add(key)

    def _validate_action_points(self):
        seen = set()

        for row in self.action_points or []:
            if not row.action_title:
                frappe.throw(_("Each action point must include an action title."))
            if not row.assigned_user:
                frappe.throw(_("Each action point must include an assigned user."))
            if not frappe.db.exists("User", {"name": row.assigned_user, "enabled": 1, "user_type": "System User"}):
                frappe.throw(_("Assigned user {0} is not an enabled System User.").format(row.assigned_user))
            if not row.due_date:
                frappe.throw(_("Each action point must include a due date."))
            if self.memo_date and row.due_date < self.memo_date:
                frappe.throw(
                    _("Action point due date for {0} cannot be earlier than the memo date.").format(
                        row.action_title
                    )
                )
            if row.status not in ACTION_POINT_STATUSES:
                frappe.throw(_("Invalid action point status for {0}.").format(row.action_title))

            key = (row.action_title.lower(), row.assigned_user)
            if key in seen:
                frappe.throw(
                    _("Duplicate action point detected for {0} and user {1}.").format(
                        row.action_title, row.assigned_user
                    )
                )
            seen.add(key)

    def can_current_user_approve(self, user=None):
        user = user or frappe.session.user
        return user == self.approver or has_approval_access(user) or has_global_access(user)

    def can_current_user_recirculate(self, user=None):
        user = user or frappe.session.user
        return user == self.owner or self.can_current_user_approve(user)

    def _get_recipient_rows_for_user(self, user=None, require_acknowledgement=False):
        user = user or frappe.session.user
        rows = [row for row in self.recipients or [] if row.user_id == user]
        if require_acknowledgement:
            rows = [row for row in rows if row.requires_acknowledgement]
        return rows

    def _can_current_user_update_action_point(self, row, user=None):
        user = user or frappe.session.user
        if user == self.owner or has_global_access(user) or has_approval_access(user):
            return True

        return row.assigned_user == user

    def _get_action_point_row(self, row_name):
        for row in self.action_points or []:
            if row.name == row_name:
                return row

        frappe.throw(_("Action point row {0} was not found.").format(row_name))

    def _append_routing_log(self, routing_action, actor=None, target_user=None, target_employee=None, remarks=None):
        actor = actor or frappe.session.user
        self.append(
            "routing_history",
            {
                "routing_action": routing_action,
                "actor": actor,
                "actor_name": get_fullname(actor),
                "target_user": target_user,
                "target_employee": target_employee,
                "action_time": now_datetime(),
                "remarks": cstr(remarks).strip(),
            },
        )

    def _save_from_system_action(self):
        self.flags.memo_system_write = True
        self.save(ignore_permissions=True)

    def apply_workflow_transition_side_effects(self):
        """Apply Memo business rules for a transition selected by Workflow.

        This method intentionally does not save. Frappe's ``apply_workflow``
        saves the document after the synchronous transition task completes.
        """
        previous_status = frappe.db.get_value("Memo", self.name, "status")
        next_status = self.status
        actor = frappe.session.user

        if previous_status == next_status:
            return
        if (previous_status, next_status) not in {
            ("Draft", "Pending Approval"),
            ("Rejected", "Amended"),
            ("Amended", "Pending Approval"),
            ("Draft", "Approved"),
            ("Amended", "Approved"),
            ("Pending Approval", "Approved"),
            ("Pending Approval", "Rejected"),
        }:
            frappe.throw(_("Invalid memo workflow transition from {0} to {1}.").format(
                previous_status, next_status
            ))

        if previous_status in EDITABLE_STATUSES:
            if actor != self.owner and not has_global_access(actor):
                frappe.throw(_("Only the memo owner can submit this memo."), frappe.PermissionError)
            if previous_status == "Amended" and (
                not self.amended_on or not self._has_meaningful_amendment()
            ):
                frappe.throw(_("Modify and save the rejected memo before resubmitting it."))
            if next_status == "Pending Approval" and not self.requires_approval:
                frappe.throw(_("This memo does not require approval."))
            if next_status == "Approved" and self.requires_approval:
                frappe.throw(_("This memo must be submitted for approval."))

        if previous_status == "Rejected":
            if actor != self.owner and not has_global_access(actor):
                frappe.throw(_("Only the memo owner or authorized staff can start an amendment."), frappe.PermissionError)
            self.flags.memo_system_write = True
            # Backfill the baseline for memos rejected before amendment
            # tracking was introduced.
            self.rejection_snapshot_hash = self.rejection_snapshot_hash or self._amendment_hash()
            self.amended_by = None
            self.amended_on = None
            self._append_routing_log(
                "Amendment Started", actor=actor, target_user=self.owner,
                remarks=_("Rejected memo unlocked for amendment."),
            )
            self.add_comment("Info", _("Amendment started by {0}.").format(get_fullname(actor)))
            return

        if previous_status == "Pending Approval" and not self.can_current_user_approve(actor):
            frappe.throw(_("You do not have permission to decide this memo."), frappe.PermissionError)

        if previous_status == "Pending Approval":
            # Workflow receives a browser-supplied document. Before bypassing
            # the destination state's role check, ensure the approver has not
            # changed any memo business content in the same request.
            stored = frappe.get_doc("Memo", self.name)
            if stored._amendment_hash(exclude_tables={"action_points"}) != self._amendment_hash(
                exclude_tables={"action_points"}
            ):
                frappe.throw(_("Approvers may only change Execution and Follow-up before deciding this memo."))
            self.flags.ignore_permissions = True

        self.flags.memo_system_write = True
        if next_status == "Pending Approval":
            self._set_default_approver()
            if not self.approver:
                frappe.throw(_("Set an approver before submitting this memo for approval."))
            self.rejected_by = None
            self.rejected_on = None
            self.approved_by = None
            self.approved_on = None
            self.approval_remarks = ""
            self._clear_circulation_state()
            self._append_routing_log(
                "Submitted for Approval", actor=actor, target_user=self.approver,
                remarks=_("Memo submitted for approval."),
            )
            self.add_comment("Info", _("Memo submitted by {0} for approval.").format(get_fullname(actor)))
            self._notify_users(
                users=[self.approver], emails=[],
                subject=_("Memo Awaiting Approval: {0}").format(self.subject),
                heading=_("A memo is awaiting your approval."),
            )
            self._set_approval_share(write=True)
            self._assign_approval_todo()
        elif next_status == "Approved":
            self._set_approval_share(write=False)
            self._close_approval_todos()
            staged_remarks = frappe.db.get_value("Memo", self.name, "approval_remarks")
            self.approval_remarks = cstr(self.approval_remarks or staged_remarks).strip()
            self.approved_by = actor
            self.approved_on = now_datetime()
            self._mark_ready_for_circulation(actor)
            self._append_routing_log(
                "Approved and Circulated", actor=actor,
                remarks=self.approval_remarks or _("Memo approved and circulated."),
            )
            self.add_comment("Info", _("Memo approved by {0}.").format(get_fullname(actor)))
            self._notify_recipients(
                _("Approved Memo: {0}").format(self.subject),
                _("A memo addressed to you has been approved."),
            )
            if previous_status == "Pending Approval":
                self._notify_users(
                    users=[self.owner], emails=[],
                    subject=_("Your memo was approved: {0}").format(self.subject),
                    heading=_("Your memo has been approved."),
                )
        else:
            self._set_approval_share(write=False)
            self._close_approval_todos()
            staged_remarks = frappe.db.get_value("Memo", self.name, "approval_remarks")
            remarks = cstr(self.approval_remarks or staged_remarks).strip()
            if not remarks:
                frappe.throw(_("Enter rejection remarks before rejecting the memo."))
            self.approval_remarks = remarks
            self.rejected_by = actor
            self.rejected_on = now_datetime()
            self.rejection_snapshot_hash = self._amendment_hash()
            self.amended_by = None
            self.amended_on = None
            self.approved_by = None
            self.approved_on = None
            self._clear_circulation_state()
            self._append_routing_log(
                "Rejected", actor=actor, target_user=self.owner, remarks=remarks,
            )
            self.add_comment("Info", _("Memo rejected by {0}.").format(get_fullname(actor)))
            self._notify_users(
                users=[self.owner], emails=[],
                subject=_("Your memo was rejected: {0}").format(self.subject),
                heading=_("Your memo was rejected."),
            )

    def _assign_approval_todo(self):
        """Put a pending memo in the selected approver's assignment dashboard."""
        if not self.approver:
            return

        from frappe.desk.form.assign_to import _add

        _add(
            {
                "assign_to": [self.approver],
                "doctype": self.doctype,
                "name": self.name,
                "description": _("Approve or reject memo {0}: {1}").format(self.name, self.subject),
                "priority": "High" if self.priority in {"High", "Urgent"} else "Medium",
                "assigned_by": frappe.session.user,
            },
            ignore_permissions=True,
        )

    def _set_approval_share(self, write=False):
        """Grant access only to this memo and remove transition write afterward."""
        if not self.approver:
            return

        from frappe.share import add_docshare

        add_docshare(
            self.doctype,
            self.name,
            user=self.approver,
            read=1,
            write=1 if write else 0,
            share=1,
            notify=0,
            flags={"ignore_share_permission": True},
        )

    def _set_owner_share(self):
        """Keep this memo accessible to its creator despite User Permissions."""
        if not self.owner:
            return

        from frappe.share import add_docshare

        add_docshare(
            self.doctype,
            self.name,
            user=self.owner,
            read=1,
            write=1,
            share=1,
            notify=0,
            flags={"ignore_share_permission": True},
        )

    def _sync_participant_shares(self):
        """Give each memo participant read, print, and share access to this memo only."""
        from frappe.share import add_docshare

        participants = {self.owner, self.approver}
        participants.update(row.user_id for row in (self.recipients or []) if row.user_id)
        participants.update(row.assigned_user for row in (self.action_points or []) if row.assigned_user)

        for user in participants - {None, "", "Guest"}:
            add_docshare(
                self.doctype,
                self.name,
                user=user,
                read=1,
                write=1 if user == self.owner or (
                    self.status == "Pending Approval" and user == self.approver
                ) else 0,
                share=1,
                notify=0,
                flags={"ignore_share_permission": True},
            )

    def _close_approval_todos(self):
        """Remove a decided memo from approval assignment dashboards."""
        from frappe.desk.form.assign_to import close_all_assignments

        close_all_assignments(self.doctype, self.name, ignore_permissions=True)

    def submit_for_approval_action(self):
        if frappe.session.user != self.owner and not has_global_access():
            frappe.throw(_("Only the memo owner can submit this memo."), frappe.PermissionError)

        if self.status not in EDITABLE_STATUSES:
            frappe.throw(_("Only draft or amended memos can be submitted."))

        if self.status == "Amended" and (
            not self.amended_on or not self._has_meaningful_amendment()
        ):
            frappe.throw(_("Modify and save the rejected memo before resubmitting it."))

        if self.requires_approval:
            self._set_default_approver()
            if not self.approver:
                frappe.throw(_("Set an approver before submitting this memo for approval."))

            self.status = "Pending Approval"
            self.approved_by = None
            self.approved_on = None
            self.approval_remarks = ""
            self._clear_circulation_state()
            self._append_routing_log(
                "Submitted for Approval",
                actor=frappe.session.user,
                target_user=self.approver,
                remarks=_("Memo submitted for approval."),
            )
        else:
            self.status = "Approved"
            self.approved_by = frappe.session.user
            self.approved_on = now_datetime()
            self.approval_remarks = ""
            self._mark_ready_for_circulation(frappe.session.user)
            self._append_routing_log(
                "Approved and Circulated",
                actor=frappe.session.user,
                remarks=_("Memo approved automatically and circulated."),
            )

        self._save_from_system_action()
        self.add_comment(
            "Info",
            _("Memo submitted by {0} and moved to status {1}.").format(
                get_fullname(frappe.session.user), self.status
            ),
        )

        if self.status == "Pending Approval":
            self._notify_users(
                users=[self.approver],
                emails=[],
                subject=_("Memo Awaiting Approval: {0}").format(self.subject),
                heading=_("A memo is awaiting your approval."),
            )
        else:
            self._notify_recipients(
                _("Approved Memo: {0}").format(self.subject),
                _("A memo has been approved and is now available to recipients."),
            )

        return {"status": self.status, "name": self.name}

    def approve_action(self, remarks=None):
        if not self.can_current_user_approve():
            frappe.throw(_("You do not have permission to approve this memo."), frappe.PermissionError)

        if self.status != "Pending Approval":
            frappe.throw(_("Only memos pending approval can be approved."))

        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_on = now_datetime()
        self.rejected_by = None
        self.rejected_on = None
        self.approval_remarks = cstr(remarks).strip()
        self._mark_ready_for_circulation(frappe.session.user)
        self._append_routing_log(
            "Approved and Circulated",
            actor=frappe.session.user,
            remarks=self.approval_remarks or _("Memo approved and circulated."),
        )
        self._save_from_system_action()
        self.add_comment(
            "Info",
            _("Memo approved by {0}.").format(get_fullname(frappe.session.user)),
        )

        self._notify_recipients(
            _("Approved Memo: {0}").format(self.subject),
            _("A memo addressed to you has been approved."),
        )
        self._notify_users(
            users=[self.owner],
            emails=[],
            subject=_("Your memo was approved: {0}").format(self.subject),
            heading=_("Your memo has been approved."),
        )
        return {"status": self.status, "name": self.name}

    def reject_action(self, remarks):
        if not self.can_current_user_approve():
            frappe.throw(_("You do not have permission to reject this memo."), frappe.PermissionError)

        if self.status != "Pending Approval":
            frappe.throw(_("Only memos pending approval can be rejected."))

        remarks = cstr(remarks).strip()
        if not remarks:
            frappe.throw(_("Enter rejection remarks before rejecting the memo."))

        self.status = "Rejected"
        self.rejected_by = frappe.session.user
        self.rejected_on = now_datetime()
        self.approved_by = None
        self.approved_on = None
        self.approval_remarks = remarks
        self._clear_circulation_state()
        self._append_routing_log(
            "Rejected",
            actor=frappe.session.user,
            target_user=self.owner,
            remarks=remarks,
        )
        self._save_from_system_action()
        self.add_comment(
            "Info",
            _("Memo rejected by {0}.").format(get_fullname(frappe.session.user)),
        )

        self._notify_users(
            users=[self.owner],
            emails=[],
            subject=_("Your memo was rejected: {0}").format(self.subject),
            heading=_("Your memo was rejected."),
        )
        return {"status": self.status, "name": self.name}

    def recirculate_action(self, remarks=None):
        if not self.can_current_user_recirculate():
            frappe.throw(_("You do not have permission to re-circulate this memo."), frappe.PermissionError)

        if self.status != "Approved":
            frappe.throw(_("Only approved memos can be re-circulated."))

        remarks = cstr(remarks).strip()
        self._mark_ready_for_circulation(frappe.session.user)
        self._append_routing_log(
            "Re-circulated",
            actor=frappe.session.user,
            remarks=remarks or _("Memo re-circulated to recipients."),
        )
        self._save_from_system_action()
        self.add_comment(
            "Info",
            _("Memo re-circulated by {0}.").format(get_fullname(frappe.session.user)),
        )

        self._notify_recipients(
            _("Re-circulated Memo: {0}").format(self.subject),
            _("A memo has been re-circulated to you."),
        )
        return {"status": self.status, "name": self.name}

    def acknowledge_action(self, remarks=None):
        if self.status != "Approved":
            frappe.throw(_("Only approved memos can be acknowledged."))

        rows = self._get_recipient_rows_for_user(frappe.session.user, require_acknowledgement=True)
        if not rows:
            frappe.throw(_("You do not have any acknowledgement responsibility on this memo."), frappe.PermissionError)

        pending_rows = [row for row in rows if row.acknowledgement_status != "Acknowledged"]
        if not pending_rows:
            frappe.throw(_("You have already acknowledged this memo."))

        remarks = cstr(remarks).strip()
        acknowledged_at = now_datetime()
        for row in pending_rows:
            row.acknowledgement_status = "Acknowledged"
            row.acknowledged_by = frappe.session.user
            row.acknowledged_on = acknowledged_at
            row.acknowledgement_remarks = remarks

        target_employee = pending_rows[0].employee
        self._append_routing_log(
            "Acknowledged",
            actor=frappe.session.user,
            target_user=frappe.session.user,
            target_employee=target_employee,
            remarks=remarks or _("Memo receipt acknowledged."),
        )
        self._save_from_system_action()
        self.add_comment(
            "Info",
            _("Memo acknowledged by {0}.").format(get_fullname(frappe.session.user)),
        )

        notify_users = [self.owner]
        if self.approver and self.approver not in notify_users:
            notify_users.append(self.approver)

        self._notify_users(
            users=notify_users,
            emails=[],
            subject=_("Memo Acknowledged: {0}").format(self.subject),
            heading=_("A recipient has acknowledged this memo."),
        )
        return {"status": self.status, "name": self.name, "acknowledged_rows": len(pending_rows)}

    def update_action_point_status_action(self, row_name, status, completion_notes=None):
        if self.status != "Approved":
            frappe.throw(_("Action points can only be updated after the memo is approved and circulated."))

        row = self._get_action_point_row(row_name)
        if not self._can_current_user_update_action_point(row):
            frappe.throw(_("You do not have permission to update this action point."), frappe.PermissionError)

        status = cstr(status).strip()
        if status not in ACTION_POINT_STATUSES:
            frappe.throw(_("Invalid action point status."))

        completion_notes = cstr(completion_notes).strip()
        row.status = status
        row.completion_notes = completion_notes

        if status == "Completed":
            row.completed_by = frappe.session.user
            row.completed_on = now_datetime()
        else:
            row.completed_by = None
            row.completed_on = None

        self._append_routing_log(
            "Action Point Updated",
            actor=frappe.session.user,
            target_user=row.assigned_user,
            target_employee=row.assigned_employee,
            remarks=_("{0} set to {1}.").format(row.action_title, status)
            + (f" {completion_notes}" if completion_notes else ""),
        )
        self._save_from_system_action()
        self.add_comment(
            "Info",
            _("Action point {0} updated to {1} by {2}.").format(
                row.action_title, status, get_fullname(frappe.session.user)
            ),
        )

        notify_users = [self.owner]
        if row.assigned_user and row.assigned_user not in notify_users:
            notify_users.append(row.assigned_user)
        if self.approver and self.approver not in notify_users:
            notify_users.append(self.approver)

        self._notify_users(
            users=notify_users,
            emails=[],
            subject=_("Memo Action Point Updated: {0}").format(self.subject),
            heading=_("An action point on this memo was updated."),
        )
        return {"status": self.status, "name": self.name, "action_point_status": status}

    def _notify_recipients(self, subject, heading):
        users = []
        emails = []
        for row in self.recipients or []:
            if row.user_id:
                users.append(row.user_id)
            if row.official_mail:
                emails.append(row.official_mail)

        self._notify_users(users, emails, subject, heading)

    def _notify_users(self, users, emails, subject, heading):
        unique_users = [user for user in dict.fromkeys(users) if user]
        unique_emails = [email for email in dict.fromkeys(emails) if email]

        message = self._build_email_message(heading)

        for user in unique_users:
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "subject": subject,
                    "email_content": message,
                    "for_user": user,
                    "document_type": "Memo",
                    "document_name": self.name,
                    "from_user": frappe.session.user,
                }
            ).insert(ignore_permissions=True)

        # Restricted memos stay inside the authenticated system; recipient
        # email addresses must not receive their content or metadata.
        if (
            self.confidentiality != "Restricted"
            and get_memo_settings().enable_email_notifications
            and unique_emails
        ):
            frappe.sendmail(
                recipients=unique_emails,
                subject=subject,
                message=message,
                reference_doctype="Memo",
                reference_name=self.name,
                delayed=False,
            )

    def _build_email_message(self, heading):
        reference_rows = []
        action_rows = []
        sign_off_rows = []

        if self.material_request:
            reference_rows.append(("Material Request", self.material_request))
        if self.purchase_order:
            reference_rows.append(("Purchase Order", self.purchase_order))
        for row in self.reference_documents or []:
            reference_rows.append((row.reference_doctype, row.reference_name))

        for row in self.action_points or []:
            action_rows.append(
                (
                    row.action_title,
                    row.assigned_employee_name or row.assigned_employee,
                    formatdate(row.due_date) if row.due_date else "",
                    row.status,
                )
            )

        sign_off_rows = [
            (_("Prepared By"), self.prepared_by, self.prepared_on),
            (_("Approved By"), self.approved_by, self.approved_on),
            (_("Circulated By"), self.circulated_by, self.circulated_on),
        ]

        rendered_reference_rows = "".join(
            f"<li><strong>{frappe.utils.escape_html(doctype)}</strong>: {frappe.utils.escape_html(name)}</li>"
            for doctype, name in reference_rows
        )
        rendered_action_rows = "".join(
            "<li><strong>{}</strong>: {} | {} | {}</li>".format(
                frappe.utils.escape_html(title),
                frappe.utils.escape_html(assignee or ""),
                frappe.utils.escape_html(due_date or ""),
                frappe.utils.escape_html(status or ""),
            )
            for title, assignee, due_date, status in action_rows
        )
        rendered_sign_off_rows = "".join(
            "<li><strong>{}</strong>: {}{}</li>".format(
                frappe.utils.escape_html(label),
                frappe.utils.escape_html(get_fullname(user) if user else ""),
                f" ({frappe.utils.escape_html(format_datetime(timestamp))})" if timestamp else "",
            )
            for label, user, timestamp in sign_off_rows
            if user or timestamp
        )

        if rendered_reference_rows:
            rendered_reference_rows = f"<ul>{rendered_reference_rows}</ul>"
        else:
            rendered_reference_rows = "<p>No related documents were attached to this memo.</p>"

        if rendered_action_rows:
            rendered_action_rows = f"<ul>{rendered_action_rows}</ul>"
        else:
            rendered_action_rows = "<p>No action points were attached to this memo.</p>"

        if rendered_sign_off_rows:
            rendered_sign_off_rows = f"<ul>{rendered_sign_off_rows}</ul>"
        else:
            rendered_sign_off_rows = "<p>No sign-off details have been captured yet.</p>"

        acknowledgement_note = ""
        if self.require_recipient_acknowledgement and self.acknowledgement_due_date:
            acknowledgement_note = _(
                "Recipient acknowledgement is required by {0}."
            ).format(formatdate(self.acknowledgement_due_date))

        return f"""
        <p>{frappe.utils.escape_html(heading)}</p>
        <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Memo No.</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{frappe.utils.escape_html(self.name)}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Subject</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{frappe.utils.escape_html(self.subject)}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{frappe.utils.escape_html(self.status)}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Memo Date</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{formatdate(self.memo_date)}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{frappe.utils.escape_html(self.originator_name or "")}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Confidentiality</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{frappe.utils.escape_html(self.confidentiality or "")}</td></tr>
        </table>
        <p><strong>Summary</strong></p>
        <p>{frappe.utils.escape_html(self.summary or self.subject)}</p>
        <p><strong>Acknowledgement Requirement</strong></p>
        <p>{frappe.utils.escape_html(acknowledgement_note or _("No acknowledgement is required for this memo."))}</p>
        <p><strong>Related Documents</strong></p>
        {rendered_reference_rows}
        <p><strong>Action Points</strong></p>
        {rendered_action_rows}
        <p><strong>Sign-off</strong></p>
        {rendered_sign_off_rows}
        <p><a href="{get_url_to_form('Memo', self.name)}">Open Memo</a></p>
        """


@frappe.whitelist()
def get_current_origin_details():
    """Return the signed-in creator details for immediate new-form display."""
    user = frappe.session.user
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user},
        ["name", "employee_name", "designation", "department", "company"],
        as_dict=True,
    )
    return {
        "prepared_by": user,
        "origin_employee": employee.name if employee else None,
        "originator_name": employee.employee_name if employee else (get_fullname(user) or user),
        "originator_designation": employee.designation if employee else None,
        "department": employee.department if employee else None,
        "company": employee.company if employee else None,
    }


@frappe.whitelist()
def get_memo_capabilities(name=None):
    """Return server-authoritative capabilities for rendering form actions."""
    result = {
        "has_global_access": has_global_access(),
        "has_approval_access": has_approval_access(),
    }
    if name:
        doc = frappe.get_doc("Memo", name)
        result.update(
            {
                "can_approve": doc.can_current_user_approve(),
                "can_recirculate": doc.can_current_user_recirculate(),
            }
        )
    return result


def process_memo_workflow_transition(doc):
    """Synchronous standard Workflow Transition Task registered in hooks.py."""
    if doc.doctype != "Memo":
        frappe.throw(_("The memo workflow task can only process Memo documents."))
    doc.apply_workflow_transition_side_effects()


@frappe.whitelist()
def set_workflow_remarks(name, remarks=None):
    """Stage approval/rejection remarks before the standard Workflow action."""
    doc = frappe.get_doc("Memo", name)
    if doc.status != "Pending Approval" or not doc.can_current_user_approve():
        frappe.throw(_("You do not have permission to decide this memo."), frappe.PermissionError)
    remarks = cstr(remarks).strip()
    frappe.db.set_value("Memo", name, "approval_remarks", remarks, update_modified=False)
    return {"name": name, "remarks": remarks}


@frappe.whitelist()
def submit_for_approval(name):
    from frappe.model.workflow import apply_workflow

    doc = frappe.get_doc("Memo", name)
    action = "Submit for Approval" if doc.requires_approval else "Approve and Circulate"
    return apply_workflow(doc, action)


@frappe.whitelist()
def approve_memo(name, remarks=None):
    from frappe.model.workflow import apply_workflow

    doc = frappe.get_doc("Memo", name)
    if doc.status != "Pending Approval" or not doc.can_current_user_approve():
        frappe.throw(_("You do not have permission to approve this memo."), frappe.PermissionError)
    doc.approval_remarks = cstr(remarks).strip()
    return apply_workflow(doc, "Approve Memo")


@frappe.whitelist()
def reject_memo(name, remarks=None):
    from frappe.model.workflow import apply_workflow

    doc = frappe.get_doc("Memo", name)
    if doc.status != "Pending Approval" or not doc.can_current_user_approve():
        frappe.throw(_("You do not have permission to reject this memo."), frappe.PermissionError)
    remarks = cstr(remarks).strip()
    if not remarks:
        frappe.throw(_("Enter rejection remarks before rejecting the memo."))
    doc.approval_remarks = remarks
    return apply_workflow(doc, "Reject Memo")


@frappe.whitelist()
def recirculate_memo(name, remarks=None):
    doc = frappe.get_doc("Memo", name)
    return doc.recirculate_action(remarks)


@frappe.whitelist()
def acknowledge_memo(name, remarks=None):
    doc = frappe.get_doc("Memo", name)
    return doc.acknowledge_action(remarks)


@frappe.whitelist()
def update_action_point_status(name, row_name, status, completion_notes=None):
    doc = frappe.get_doc("Memo", name)
    return doc.update_action_point_status_action(row_name, status, completion_notes)
