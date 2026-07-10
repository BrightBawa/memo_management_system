frappe.ui.form.on("Memo Settings", {
    refresh(frm) {
        if (!frappe.user.has_role(["System Manager", "Memo Administrator"])) {
            return;
        }

        frm.add_custom_button(__("Sync Employee Memo Access"), () => {
            frappe.call("memo_management_system.memo_management_system.doctype.memo_settings.memo_settings.sync_employee_roles").then(() => {
                frappe.show_alert({ message: __("Memo access synced to employee users."), indicator: "green" });
            });
        });
    },
});
