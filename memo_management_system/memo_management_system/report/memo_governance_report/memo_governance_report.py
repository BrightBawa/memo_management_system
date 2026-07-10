import frappe
from frappe import _

from memo_management_system.api.permissions import get_memo_permission_query_conditions


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "fieldname": "name",
            "label": _("Memo"),
            "fieldtype": "Link",
            "options": "Memo",
            "width": 170,
        },
        {
            "fieldname": "memo_date",
            "label": _("Memo Date"),
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "fieldname": "subject",
            "label": _("Subject"),
            "fieldtype": "Data",
            "width": 260,
        },
        {
            "fieldname": "department",
            "label": _("Department"),
            "fieldtype": "Link",
            "options": "Department",
            "width": 140,
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "fieldname": "priority",
            "label": _("Priority"),
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "fieldname": "originator_name",
            "label": _("Originator"),
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "fieldname": "approver",
            "label": _("Approver"),
            "fieldtype": "Link",
            "options": "User",
            "width": 180,
        },
        {
            "fieldname": "total_recipients",
            "label": _("Recipients"),
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "fieldname": "acknowledged_recipients",
            "label": _("Acknowledged"),
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "fieldname": "open_action_points",
            "label": _("Open Actions"),
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "fieldname": "overdue_action_points",
            "label": _("Overdue Actions"),
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "fieldname": "circulated_on",
            "label": _("Circulated On"),
            "fieldtype": "Datetime",
            "width": 155,
        },
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.from_date:
        conditions.append("memo.memo_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.to_date:
        conditions.append("memo.memo_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.department:
        conditions.append("memo.department = %(department)s")
        values["department"] = filters.department

    if filters.status:
        conditions.append("memo.status = %(status)s")
        values["status"] = filters.status

    if filters.priority:
        conditions.append("memo.priority = %(priority)s")
        values["priority"] = filters.priority

    if filters.approver:
        conditions.append("memo.approver = %(approver)s")
        values["approver"] = filters.approver

    permission_condition = get_memo_permission_query_conditions(frappe.session.user)
    if permission_condition:
        conditions.append(permission_condition.replace("`tabMemo`", "memo"))

    where_clause = " and ".join(conditions) if conditions else "1=1"

    return frappe.db.sql(
        f"""
        select
            memo.name,
            memo.memo_date,
            memo.subject,
            memo.department,
            memo.status,
            memo.priority,
            memo.originator_name,
            memo.approver,
            memo.circulated_on,
            coalesce(rec.total_recipients, 0) as total_recipients,
            coalesce(rec.acknowledged_recipients, 0) as acknowledged_recipients,
            coalesce(act.open_action_points, 0) as open_action_points,
            coalesce(act.overdue_action_points, 0) as overdue_action_points
        from `tabMemo` memo
        left join (
            select
                parent,
                count(*) as total_recipients,
                sum(case when acknowledgement_status = 'Acknowledged' then 1 else 0 end) as acknowledged_recipients
            from `tabMemo recipient`
            group by parent
        ) rec on rec.parent = memo.name
        left join (
            select
                parent,
                sum(case when status in ('Open', 'In Progress') then 1 else 0 end) as open_action_points,
                sum(case when status in ('Open', 'In Progress') and due_date < curdate() then 1 else 0 end) as overdue_action_points
            from `tabMemo Action Point`
            group by parent
        ) act on act.parent = memo.name
        where {where_clause}
        order by memo.memo_date desc, memo.modified desc
        """,
        values,
        as_dict=True,
    )
