app_name = "memo_management_system"
app_title = "Memo Management System"
app_publisher = "Bright Bawa"
app_description = "A memo management system is a digital solution that helps users create, organize, store, and manage memos or notes efficiently. It streamlines communication and information tracking by allowing easy access, editing, categorization, and sharing of important memos within an app or organization."
app_email = "brightbawa11@gmail.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext", "hrms"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "memo_management_system",
# 		"logo": "/assets/memo_management_system/logo.png",
# 		"title": "Memo Management System",
# 		"route": "/memo_management_system",
# 		"has_permission": "memo_management_system.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/memo_management_system/css/memo_management_system.css"
# app_include_js = "/assets/memo_management_system/js/memo_management_system.js"

# include js, css files in header of web template
# web_include_css = "/assets/memo_management_system/css/memo_management_system.css"
# web_include_js = "/assets/memo_management_system/js/memo_management_system.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "memo_management_system/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "memo_management_system/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "memo_management_system.utils.jinja_methods",
# 	"filters": "memo_management_system.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "memo_management_system.install.before_install"
after_install = "memo_management_system.install.after_install"
after_migrate = "memo_management_system.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "memo_management_system.uninstall.before_uninstall"
# after_uninstall = "memo_management_system.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "memo_management_system.utils.before_app_install"
# after_app_install = "memo_management_system.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "memo_management_system.utils.before_app_uninstall"
# after_app_uninstall = "memo_management_system.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "memo_management_system.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "memo_management_system.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Memo": "memo_management_system.api.permissions.get_memo_permission_query_conditions",
}

has_permission = {
    "Memo": "memo_management_system.api.permissions.has_memo_permission",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Employee": {
        "after_insert": "memo_management_system.utils.memo.sync_memo_access_for_employee_doc",
        "on_update": "memo_management_system.utils.memo.sync_memo_access_for_employee_doc",
    },
    "User": {
        "after_insert": "memo_management_system.utils.memo.sync_memo_access_for_user_doc",
        "on_update": "memo_management_system.utils.memo.sync_memo_access_for_user_doc",
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"memo_management_system.tasks.all"
# 	],
# 	"daily": [
# 		"memo_management_system.tasks.daily"
# 	],
# 	"hourly": [
# 		"memo_management_system.tasks.hourly"
# 	],
# 	"weekly": [
# 		"memo_management_system.tasks.weekly"
# 	],
# 	"monthly": [
# 		"memo_management_system.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "memo_management_system.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "memo_management_system.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "memo_management_system.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "memo_management_system.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["memo_management_system.utils.before_request"]
# after_request = ["memo_management_system.utils.after_request"]

# Job Events
# ----------
# before_job = ["memo_management_system.utils.before_job"]
# after_job = ["memo_management_system.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"memo_management_system.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
