const approvalRoles = ["System Manager", "Memo Approver", "Memo Manager", "Memo Administrator"];

const setEmployeeQuery = (frm) => {
    if (frm.fields_dict.recipients?.grid) {
        frm.fields_dict.recipients.grid.get_field("employee").get_query = () => ({
            filters: { status: "Active" },
        });
    }

    if (frm.fields_dict.action_points?.grid) {
        frm.fields_dict.action_points.grid.get_field("assigned_employee").get_query = () => ({
            filters: { status: "Active" },
        });
    }
};

const syncRecipientAcknowledgementDefaults = (frm) => {
    (frm.doc.recipients || []).forEach((row) => {
        if (
            frm.doc.require_recipient_acknowledgement &&
            (row.requires_acknowledgement === undefined || row.acknowledgement_status === "Not Required")
        ) {
            row.requires_acknowledgement = 1;
        }

        if (row.requires_acknowledgement && frm.doc.acknowledgement_due_date && !row.acknowledgement_due_date) {
            row.acknowledgement_due_date = frm.doc.acknowledgement_due_date;
        }

        if (!row.requires_acknowledgement) {
            row.acknowledgement_due_date = null;
        }
    });

    frm.refresh_field("recipients");
};

const lockReadonlyGrids = (frm) => {
    const routingGrid = frm.fields_dict.routing_history?.grid;
    if (!routingGrid) {
        return;
    }

    routingGrid.cannot_add_rows = true;
    routingGrid.cannot_delete_rows = true;
    routingGrid.refresh();
};

const getAccessibleActionPoints = (frm) => {
    const canManageAll =
        frm.doc.owner === frappe.session.user || frappe.user.has_role(approvalRoles);

    return (frm.doc.action_points || []).filter((row) => {
        if (["Completed", "Cancelled"].includes(row.status)) {
            return false;
        }

        return canManageAll || row.assigned_user === frappe.session.user;
    });
};

const addMemoButtons = (frm) => {
    if (frm.is_new()) {
        return;
    }

    if (["Draft", "Rejected"].includes(frm.doc.status) && frm.perm[0]?.write) {
        const label = frm.doc.requires_approval ? __("Submit for Approval") : __("Approve and Circulate");
        frm.add_custom_button(label, () => {
            frappe.call("memo_management_system.memo_management_system.doctype.memo.memo.submit_for_approval", {
                name: frm.doc.name,
            }).then(() => frm.reload_doc());
        });
    }

    const canApprove =
        frm.doc.status === "Pending Approval" &&
        (frm.doc.approver === frappe.session.user || frappe.user.has_role(approvalRoles));

    if (canApprove) {
        frm.add_custom_button(__("Approve Memo"), () => {
            frappe.prompt(
                [
                    {
                        fieldname: "remarks",
                        fieldtype: "Small Text",
                        label: __("Approval Remarks"),
                    },
                ],
                (values) => {
                    frappe.call("memo_management_system.memo_management_system.doctype.memo.memo.approve_memo", {
                        name: frm.doc.name,
                        remarks: values.remarks,
                    }).then(() => frm.reload_doc());
                },
                __("Approve Memo"),
                __("Approve")
            );
        });

        frm.add_custom_button(__("Reject Memo"), () => {
            frappe.prompt(
                [
                    {
                        fieldname: "remarks",
                        fieldtype: "Small Text",
                        label: __("Rejection Remarks"),
                        reqd: 1,
                    },
                ],
                (values) => {
                    frappe.call("memo_management_system.memo_management_system.doctype.memo.memo.reject_memo", {
                        name: frm.doc.name,
                        remarks: values.remarks,
                    }).then(() => frm.reload_doc());
                },
                __("Reject Memo"),
                __("Reject")
            );
        });
    }

    const canRecirculate =
        frm.doc.status === "Approved" &&
        (frm.doc.owner === frappe.session.user || frappe.user.has_role(approvalRoles));

    if (canRecirculate) {
        frm.add_custom_button(__("Re-circulate Memo"), () => {
            frappe.prompt(
                [
                    {
                        fieldname: "remarks",
                        fieldtype: "Small Text",
                        label: __("Circulation Remarks"),
                    },
                ],
                (values) => {
                    frappe.call("memo_management_system.memo_management_system.doctype.memo.memo.recirculate_memo", {
                        name: frm.doc.name,
                        remarks: values.remarks,
                    }).then(() => frm.reload_doc());
                },
                __("Re-circulate Memo"),
                __("Send")
            );
        });
    }

    const canAcknowledge =
        frm.doc.status === "Approved" &&
        (frm.doc.recipients || []).some(
            (row) =>
                row.user_id === frappe.session.user &&
                row.requires_acknowledgement &&
                row.acknowledgement_status !== "Acknowledged"
        );

    if (canAcknowledge) {
        frm.add_custom_button(__("Acknowledge Receipt"), () => {
            frappe.prompt(
                [
                    {
                        fieldname: "remarks",
                        fieldtype: "Small Text",
                        label: __("Acknowledgement Remarks"),
                    },
                ],
                (values) => {
                    frappe.call("memo_management_system.memo_management_system.doctype.memo.memo.acknowledge_memo", {
                        name: frm.doc.name,
                        remarks: values.remarks,
                    }).then(() => frm.reload_doc());
                },
                __("Acknowledge Memo"),
                __("Acknowledge")
            );
        });
    }

    const actionPoints = getAccessibleActionPoints(frm);
    if (actionPoints.length) {
        const actionPointOptions = actionPoints.map(
            (row) =>
                `${row.name} :: ${row.action_title} - ${row.assigned_employee_name || row.assigned_employee} (${row.status})`
        );

        frm.add_custom_button(__("Update Action Point"), () => {
            frappe.prompt(
                [
                    {
                        fieldname: "row_name",
                        fieldtype: "Select",
                        label: __("Action Point"),
                        options: actionPointOptions.join("\n"),
                        reqd: 1,
                    },
                    {
                        fieldname: "status",
                        fieldtype: "Select",
                        label: __("New Status"),
                        options: "Open\nIn Progress\nCompleted\nCancelled",
                        reqd: 1,
                    },
                    {
                        fieldname: "completion_notes",
                        fieldtype: "Small Text",
                        label: __("Notes"),
                    },
                ],
                (values) => {
                    const [rowName] = values.row_name.split(" :: ");
                    frappe.call("memo_management_system.memo_management_system.doctype.memo.memo.update_action_point_status", {
                        name: frm.doc.name,
                        row_name: rowName,
                        status: values.status,
                        completion_notes: values.completion_notes,
                    }).then(() => frm.reload_doc());
                },
                __("Update Action Point"),
                __("Update")
            );
        });
    }
};

frappe.ui.form.on("Memo", {
    setup(frm) {
        frm.set_query("approver", () => ({
            filters: {
                enabled: 1,
                user_type: "System User",
            },
        }));
        setEmployeeQuery(frm);
    },
    onload(frm) {
        setEmployeeQuery(frm);
        lockReadonlyGrids(frm);
    },
    refresh(frm) {
        setEmployeeQuery(frm);
        lockReadonlyGrids(frm);
        addMemoButtons(frm);
    },
    require_recipient_acknowledgement(frm) {
        syncRecipientAcknowledgementDefaults(frm);
    },
    acknowledgement_due_date(frm) {
        syncRecipientAcknowledgementDefaults(frm);
    },
});

frappe.ui.form.on("Memo recipient", {
    requires_acknowledgement(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row.acknowledgement_due_date = row.requires_acknowledgement ? frm.doc.acknowledgement_due_date : null;
        frm.refresh_field("recipients");
    },
});
