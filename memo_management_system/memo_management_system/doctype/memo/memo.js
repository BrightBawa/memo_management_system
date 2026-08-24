const setUserQueries = (frm) => {
    const userFilters = {
        enabled: 1,
        user_type: "System User",
    };

    if (frm.fields_dict.recipients?.grid) {
        frm.fields_dict.recipients.grid.get_field("user_id").get_query = () => ({
            filters: userFilters,
        });
    }

    if (frm.fields_dict.action_points?.grid) {
        frm.fields_dict.action_points.grid.get_field("assigned_user").get_query = () => ({
            filters: userFilters,
        });
    }
};

const setApproverLinkLabel = (frm, userField, designationField, employeeField) => {
    const user = frm.doc[userField];
    const designation = frm.doc[designationField];
    const employee = frm.doc[employeeField];
    if (!user || !designation) {
        return;
    }

    const label = employee ? `${designation} (${employee})` : designation;
    frappe.utils.add_link_title("User", user, label);
    frm.fields_dict[userField]?.set_formatted_input(user);
};

const setApproverLinkLabels = (frm) => {
    setApproverLinkLabel(frm, "approver", "approver_designation", "approver_employee");
    setApproverLinkLabel(
        frm,
        "secondary_approver",
        "secondary_approver_designation",
        "secondary_approver_employee"
    );
};

const refreshApproverDetails = async (frm, userField, designationField, employeeField) => {
    const user = frm.doc[userField];
    if (!user) {
        await frm.set_value({[designationField]: null, [employeeField]: null});
        return;
    }

    const response = await frappe.db.get_value(
        "Employee",
        {user_id: user, status: "Active"},
        ["name", "designation"]
    );
    const employee = response.message || {};
    await frm.set_value({
        [designationField]: employee.designation || null,
        [employeeField]: employee.name || null,
    });
    setApproverLinkLabel(frm, userField, designationField, employeeField);
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

const configureExecutionAccess = (frm, capabilities = {}) => {
    const canConfigure =
        frm.doc.status === "Pending Approval" &&
        (frm.doc.approver === frappe.session.user ||
            frm.doc.secondary_approver === frappe.session.user ||
            capabilities.has_global_access ||
            capabilities.has_approval_access);
    const canView = canConfigure || frm.doc.status === "Approved";
    const grid = frm.fields_dict.action_points?.grid;

    frm.toggle_display("execution_section", canView);
    frm.toggle_display("action_points", canView);
    if (grid) {
        grid.cannot_add_rows = !canConfigure;
        grid.cannot_delete_rows = !canConfigure;
        grid.toggle_enable("action_title", canConfigure);
        grid.toggle_enable("assigned_user", canConfigure);
        grid.toggle_enable("due_date", canConfigure);
        grid.toggle_enable("priority", canConfigure);
        grid.toggle_enable("action_details", canConfigure);
        grid.refresh();
    }
};

const setCurrentUserOrigin = async (frm) => {
    if (!frm.is_new() || frm.doc.origin_employee) {
        return;
    }

    const response = await frappe.call(
        "memo_management_system.memo_management_system.doctype.memo.memo.get_current_origin_details"
    );
    const origin = response.message || {};
    await frm.set_value({
        prepared_by: origin.prepared_by,
        origin_employee: origin.origin_employee,
        originator_name: origin.originator_name,
        originator_designation: origin.originator_designation,
        department: origin.department,
        company: origin.company,
    });
};

const getAccessibleActionPoints = (frm, capabilities = {}) => {
    const canManageAll =
        frm.doc.owner === frappe.session.user ||
        capabilities.has_global_access ||
        capabilities.has_approval_access;

    return (frm.doc.action_points || []).filter((row) => {
        if (["Completed", "Cancelled"].includes(row.status)) {
            return false;
        }

        return canManageAll || row.assigned_user === frappe.session.user;
    });
};

const addMemoButtons = (frm, capabilities = {}) => {
    if (frm.is_new()) {
        return;
    }

    const canRecirculate =
        frm.doc.status === "Approved" &&
        capabilities.can_recirculate;

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

    const actionPoints =
        frm.doc.status === "Approved" ? getAccessibleActionPoints(frm, capabilities) : [];
    if (actionPoints.length) {
        const actionPointOptions = actionPoints.map(
            (row) =>
                `${row.name} :: ${row.action_title} - ${row.assigned_employee_name || row.assigned_user} (${row.status})`
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
        frm.set_query("secondary_approver", () => ({
            filters: {
                enabled: 1,
                user_type: "System User",
            },
        }));
        setUserQueries(frm);
        configureExecutionAccess(frm);
    },
    async onload(frm) {
        setUserQueries(frm);
        lockReadonlyGrids(frm);
        configureExecutionAccess(frm);
        await setCurrentUserOrigin(frm);
        setApproverLinkLabels(frm);
    },
    async refresh(frm) {
        setUserQueries(frm);
        lockReadonlyGrids(frm);
        if (frm.is_new()) {
            configureExecutionAccess(frm);
            return;
        }
        const response = await frappe.call(
            "memo_management_system.memo_management_system.doctype.memo.memo.get_memo_capabilities",
            { name: frm.doc.name }
        );
        const capabilities = response.message || {};
        configureExecutionAccess(frm, capabilities);
        addMemoButtons(frm, capabilities);
        setApproverLinkLabels(frm);
    },
    before_workflow_action(frm) {
        const action = frm.selected_workflow_action;
        if (!["Approve Memo", "Reject Memo"].includes(action)) {
            return Promise.resolve();
        }

        // Frappe freezes the page before running this hook. A prompt opened
        // while that overlay is present looks disabled and cannot reliably
        // receive pointer events, so leave the page interactive while asking
        // for remarks.
        frappe.dom.unfreeze();

        return new Promise((resolve, reject) => {
            let submitted = false;
            const dialog = frappe.prompt(
                [{
                    fieldname: "remarks",
                    fieldtype: "Small Text",
                    label: action === "Reject Memo" ? __("Rejection Remarks") : __("Approval Remarks"),
                    reqd: action === "Reject Memo" ? 1 : 0,
                }],
                (values) => {
                    submitted = true;
                    frappe.call({
                        method: "memo_management_system.memo_management_system.doctype.memo.memo.set_workflow_remarks",
                        args: {name: frm.doc.name, remarks: values.remarks || ""},
                    }).then((response) => {
                        // Keep the browser model aligned as well. The workflow
                        // task has a database fallback because Frappe may omit
                        // read-only fields while serializing frm.doc.
                        frm.doc.approval_remarks = response.message.remarks;
                        resolve();
                    }).catch((error) => {
                        frappe.dom.unfreeze();
                        reject(error);
                    });
                },
                __(action),
                action === "Reject Memo" ? __("Reject") : __("Approve")
            );
            dialog.onhide = () => {
                // frappe.prompt hides its dialog immediately before invoking
                // the submit callback. Defer the cancellation check so a
                // normal Approve/Reject click can mark the prompt submitted.
                setTimeout(() => {
                    if (!submitted) {
                        frappe.dom.unfreeze();
                        reject(new Error(__("Workflow action cancelled.")));
                    }
                }, 0);
            };
        });
    },
    require_recipient_acknowledgement(frm) {
        syncRecipientAcknowledgementDefaults(frm);
    },
    acknowledgement_due_date(frm) {
        syncRecipientAcknowledgementDefaults(frm);
    },
    requires_approval(frm) {
        // Only show the warning when the checkbox is unchecked.
        if (frm.doc.requires_approval) {
            return;
        }

        frappe.confirm(
            __(
                "Disabling approval means this memo will not be sent to an approver. " +
                "The memo may be approved and circulated directly by an authorized user. " +
                "Are you sure you want to continue?"
            ),
            () => {
                // The user selected Yes, so leave the checkbox unchecked.
                frappe.show_alert({
                    message: __("Approval requirement disabled"),
                    indicator: "orange",
                });
            },
            () => {
                // The user selected No or cancelled, so restore the checkbox.
                frm.set_value("requires_approval", 1);
            }
        );
    },
    approver(frm) {
        return refreshApproverDetails(
            frm,
            "approver",
            "approver_designation",
            "approver_employee"
        );
    },
    secondary_approver(frm) {
        return refreshApproverDetails(
            frm,
            "secondary_approver",
            "secondary_approver_designation",
            "secondary_approver_employee"
        );
    },
});

frappe.ui.form.on("Memo recipient", {
    requires_acknowledgement(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row.acknowledgement_due_date = row.requires_acknowledgement ? frm.doc.acknowledgement_due_date : null;
        frm.refresh_field("recipients");
    },
});
