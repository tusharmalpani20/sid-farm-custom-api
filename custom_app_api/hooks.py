app_name = "custom_app_api"
app_title = "Custom API"
app_publisher = "Hopnet"
app_description = "This app will allow us to create, update, delete and get list of certain doc types"
app_email = "tushar.m@hopnet.co.in"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "custom_app_api",
# 		"logo": "/assets/custom_app_api/logo.png",
# 		"title": "Custom API",
# 		"route": "/custom_app_api",
# 		"has_permission": "custom_app_api.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/custom_app_api/css/custom_app_api.css"
# app_include_js = "/assets/custom_app_api/js/custom_app_api.js"

# include js, css files in header of web template
# web_include_css = "/assets/custom_app_api/css/custom_app_api.css"
# web_include_js = "/assets/custom_app_api/js/custom_app_api.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "custom_app_api/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	# "doctype" : "public/js/doctype.js"
	"Employee" : "public/js/employee.js",
	"Additional Salary" : "public/js/additional_salary.js",
	"Route Tracking" : "public/js/route_tracking.js",
	"Delivery Records" : "public/js/delivery_records.js",
	"Visit Tracker" : "public/js/visit_tracker.js",
	"Attendance" : "public/js/attendance.js",
	"Employee Promotion" : "public/js/employee_promotion.js"
}
doctype_list_js = {
	# "doctype" : "public/js/doctype_list.js"
	"Employee" : "public/js/employee_list.js",
	"Salary Slip" : "public/js/salary_slip_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "custom_app_api/public/icons.svg"

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

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "custom_app_api.utils.jinja_methods",
# 	"filters": "custom_app_api.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "custom_app_api.install.before_install"
# after_install = "custom_app_api.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "custom_app_api.uninstall.before_uninstall"
# after_uninstall = "custom_app_api.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "custom_app_api.utils.before_app_install"
# after_app_install = "custom_app_api.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "custom_app_api.utils.before_app_uninstall"
# after_app_uninstall = "custom_app_api.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "custom_app_api.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	#"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
	"Employee": "custom_app_api.permission_query_conditions.employee.get_permission_query_conditions",
	"Route": "custom_app_api.permission_query_conditions.Route.get_permission_query_conditions",
	"Point": "custom_app_api.permission_query_conditions.Point.get_permission_query_conditions",
	"Area": "custom_app_api.permission_query_conditions.Area.get_permission_query_conditions",
	"Zone": "custom_app_api.permission_query_conditions.Zone.get_permission_query_conditions",
	"Attendance": "custom_app_api.permission_query_conditions.Attendance.get_permission_query_conditions",
	"Job Applicant": "custom_app_api.permission_query_conditions.job_applicant.get_permission_query_conditions",
	"Job Opening": "custom_app_api.permission_query_conditions.job_opening.get_permission_query_conditions"
}
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	# "ToDo": "custom_app.overrides.CustomToDo"
	"Salary Slip": "custom_app_api.overrides.doctypes.salary_slip.CustomSalarySlip"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	# "*": {
	# 	"on_update": "method",
	# 	"on_cancel": "method",
	# 	"on_trash": "method"
	# }
	"Employee": {
		"on_update": ["custom_app_api.doc_events.employee.after_save"]
	},
	"Employee Promotion": {
		"before_save": "custom_app_api.doc_events.employee_promotion.before_save",
		"before_submit": "custom_app_api.doc_events.employee_promotion.before_submit"
	},
	"Job Applicant": {
        "after_insert": "custom_app_api.cron_functions.create_employee_referral_and_additional_salary.create_employee_referral_for_job_applicant"
    },
	"Route": {
		"after_insert": "custom_app_api.doc_events.route.after_insert"
	},
	"Additional Salary": {
		"on_update": "custom_app_api.doc_events.additional_salary.on_update"
    }
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"*/30 * * * *": [
            "custom_app_api.cron_functions.create_job_vacancy.check_routes_for_vacancies",
			#"custom_app_api.cron_functions.import_routes.import_routes",
			"custom_app_api.cron_functions.import_routes_v2.import_routes_v2"
        ],
		"0 1 * * *" :[
			"custom_app_api.cron_functions.update_delivery_count_for_each_route.update_delivery_count_for_routes_v2"
		],
		"0 9 * * *": [
			"custom_app_api.cron_functions.check_attendance_index_for_route_tracking.check_attendance_index_for_route_tracking"
		],
		"30 9 * * *": [
			"custom_app_api.cron_functions.attendance_cron.auto_mark_employee_absent_and_submit_all_todays_attendance"
		],
		"45 9 * * *": [
			"custom_app_api.cron_functions.additional_salary_extra_km.calculate_extra_km_salary"
		],
		"0 10 * * *": [
			#"custom_app_api.cron_functions.email_report.send_point_wise_attendance_report"

			"custom_app_api.cron_functions.additional_salary_route_bonus.generate_route_payout"
		],
		"0 22 * * *": [
			"custom_app_api.cron_functions.create_employee_referral_and_additional_salary.process_referral_bonuses"
		],
		"30 22 * * *": [
			"custom_app_api.cron_functions.auto_assign_salary_structure_for_promotions.auto_assign_salary_structure"
		],
		"0 23 * * *": [  # Runs at 11:00 PM (23:00) every day
			"custom_app_api.cron_functions.salary_slip_cron.generate_salary_slips_for_active_employees"
		],
		"0 0 * * *": [
			"custom_app_api.cron_functions.employee.check_notice_period_completion"
		],
		"0 11 L * *": [
            # "custom_app_api.cron_functions.additional_salary_packet_bonus.calculate_packet_bonus"
        ],
	},
	# "all": [
	# 	"custom_app_api.tasks.all"
	# ],
	"daily": [
        "custom_app_api.cron_functions.calculate_employee_age.calculate_employee_age"
    ],
	"hourly": [
	  # "custom_app_api.tasks.hourly"
	  #"custom_app_api.cron_functions.salary_slip_cron.generate_salary_slips_for_active_employees",

	  "custom_app_api.cron_functions.send_auto_email_report.send_custom_time_reports"
	],
	# "weekly": [
	# 	"custom_app_api.tasks.weekly"
	# ],
	# "monthly": [
	# 	"custom_app_api.tasks.monthly"
	# ],
}

# Testing
# -------

# before_tests = "custom_app_api.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "custom_app_api.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "custom_app_api.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["custom_app_api.utils.before_request"]
# after_request = ["custom_app_api.utils.after_request"]

# Job Events
# ----------
# before_job = ["custom_app_api.utils.before_job"]
# after_job = ["custom_app_api.utils.after_job"]

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
# 	"custom_app_api.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

