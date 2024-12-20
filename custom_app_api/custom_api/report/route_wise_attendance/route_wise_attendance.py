# # Copyright (c) 2024, Hopnet and contributors
# # For license information, please see license.txt

# # import frappe


# def execute(filters=None):
# 	columns, data = [], []
# 	return columns, data


# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


from calendar import monthrange
from itertools import groupby

import frappe
from frappe import _
from frappe.query_builder.functions import Count, Extract, Sum
from frappe.utils import cint, cstr, getdate
from frappe.utils.nestedset import get_descendants_of

Filters = frappe._dict

status_map = {
	"Present": "P",
	"Absent": "A",
	"Half Day": "HD",
	"Work From Home": "WFH",
	"On Leave": "L",
	"Holiday": "H",
	"Weekly Off": "WO",
}

day_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def execute(filters: Filters | None = None) -> tuple:
	filters = frappe._dict(filters or {})

	# Automatically enable summarized view for Route, Area, Zone, Point
	if filters.group_by in ["Route", "Area", "Zone", "Point"]:
		filters.summarized_view = 1

	# Validate and process date filters
	validate_and_process_date_filters(filters)

	if filters.company:
		filters.companies = [filters.company]
		if filters.include_company_descendants:
			filters.companies.extend(get_descendants_of("Company", filters.company))

	attendance_map = get_attendance_map(filters)
	if not attendance_map:
		frappe.msgprint(_("No attendance records found."), alert=True, indicator="orange")
		return [], [], None, None

	columns = get_columns(filters)
	data = get_data(filters, attendance_map)

	if not data:
		frappe.msgprint(_("No attendance records found for this criteria."), alert=True, indicator="orange")
		return columns, [], None, None

	chart = get_chart_data(attendance_map, filters) if not filters.summarized_view else None

	return columns, data, None, chart

def validate_and_process_date_filters(filters):
	"""Validate and process date range filters"""
	if filters.date_range == "Daily":
		if not filters.specific_date:
			frappe.throw(_("Please select a date."))
		# Convert specific_date to month and year for consistency
		date_obj = getdate(filters.specific_date)
		filters.month = date_obj.month
		filters.year = date_obj.year
		# Add day filter for daily view
		filters.day = date_obj.day
	
	elif filters.date_range == "Monthly":
		if not (filters.month and filters.year):
			frappe.throw(_("Please select month and year."))
	
	elif filters.date_range == "Quarterly":
		if not (filters.quarter and filters.year):
			frappe.throw(_("Please select quarter and year."))
		# Convert quarter to month range
		quarter_mapping = {
			"Q1 (Jan-Mar)": [1, 3],
			"Q2 (Apr-Jun)": [4, 6],
			"Q3 (Jul-Sep)": [7, 9],
			"Q4 (Oct-Dec)": [10, 12]
		}
		filters.from_month, filters.to_month = quarter_mapping.get(filters.quarter, [1, 3])

def get_columns(filters: Filters) -> list[dict]:
	columns = []
	
	# Special handling for Route, Area, Zone, Point
	if filters.group_by in ["Route", "Area", "Zone", "Point"]:
		columns.extend([
			{
				"label": _(filters.group_by),
				"fieldname": frappe.scrub(filters.group_by),
				"fieldtype": "Data",
				"width": 200
			},
			{
				"label": _("Total Employees"),
				"fieldname": "total_employees",
				"fieldtype": "Int",
				"width": 120
			},
			{
				"label": _("Present"),
				"fieldname": "total_present",
				"fieldtype": "Float",
				"width": 100
			},
			{
				"label": _("Absent"),
				"fieldname": "total_absent",
				"fieldtype": "Float",
				"width": 100
			},
			{
				"label": _("On Leave"),
				"fieldname": "total_leaves",
				"fieldtype": "Float",
				"width": 100
			},
			{
				"label": _("Attendance %"),
				"fieldname": "attendance_percentage",
				"fieldtype": "Percent",
				"width": 100
			}
		])
		return columns
	
	# Standard handling for other group by options
	if filters.group_by:
		options_mapping = {
			"Branch": "Branch",
			"Grade": "Employee Grade",
			"Department": "Department",
			"Designation": "Designation",
		}
		options = options_mapping.get(filters.group_by)
		columns.append(
			{
				"label": _(filters.group_by),
				"fieldname": frappe.scrub(filters.group_by),
				"fieldtype": "Link",
				"options": options,
				"width": 120,
			}
		)

	# Add standard columns
	columns.extend([
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 135,
		},
		{
			"label": _("Employee Name"),
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 120
		}
	])

	# Add summarized view columns if needed
	if filters.summarized_view:
		columns.extend([
			# ... your summarized view columns ...
		])
	else:
		columns.append({"label": _("Shift"), "fieldname": "shift", "fieldtype": "Data", "width": 120})
		columns.extend(get_columns_for_days(filters))

	return columns


def get_data(filters: Filters, attendance_map: dict) -> list[dict]:
	# Special handling for Route, Area, Zone, Point
	if filters.group_by in ["Route", "Area", "Zone", "Point"]:
		return get_location_wise_attendance(filters, attendance_map)
	
	# Standard handling for Branch, Department, etc.
	employee_details, group_by_param_values = get_employee_related_details(filters)
	holiday_map = get_holiday_map(filters)
	data = []

	if filters.group_by:
		group_by_column = frappe.scrub(filters.group_by)

		for value in group_by_param_values:
			if not value:
				continue

			records = get_rows(employee_details[value], filters, holiday_map, attendance_map)

			if records:
				data.append({group_by_column: value})
				data.extend(records)
	else:
		data = get_rows(employee_details, filters, holiday_map, attendance_map)

	return data


def get_location_wise_attendance(filters: Filters, attendance_map: dict) -> list[dict]:
	"""Get summarized attendance data grouped by Route/Area/Zone/Point"""
	Employee = frappe.qb.DocType("Employee")
	
	# Map group_by to custom field names
	field_mapping = {
		"Route": "custom_route",
		"Area": "custom_area",
		"Zone": "custom_zone",
		"Point": "custom_point"
	}
	
	group_field = field_mapping.get(filters.group_by)
	
	# Get all unique locations and their employee counts
	locations = frappe.get_all(
		"Employee",
		fields=[
			f"{group_field} as location",
			"count(*) as total_employees"
		],
		filters={
			"company": ("in", filters.companies),
			"status": "Active"
		},
		group_by=group_field
	)

	# Process attendance data for each location
	data = []
	for loc in locations:
		if not loc.location:
			continue
		
		location_employees = frappe.get_all(
			"Employee",
			fields=["name"],
			filters={
				group_field: loc.location,
				"company": ("in", filters.companies),
				"status": "Active"
			}
		)
		
		# Initialize counters
		present = absent = leaves = 0
		
		# Count attendance for each employee in this location
		for emp in location_employees:
			if emp.name in attendance_map:
				for shift_data in attendance_map[emp.name].values():
					for status in shift_data.values():
						if status in ["Present", "Work From Home"]:
							present += 1
						elif status == "Absent":
							absent += 1
						elif status == "On Leave":
							leaves += 1
		
		# Calculate attendance percentage
		total_marked = present + absent + leaves
		attendance_percentage = (present / total_marked * 100) if total_marked else 0
		
		data.append({
			frappe.scrub(filters.group_by): loc.location,
			"total_employees": loc.total_employees,
			"total_present": present,
			"total_absent": absent,
			"total_leaves": leaves,
			"attendance_percentage": attendance_percentage
		})
	
	# Sort by attendance percentage in descending order
	data.sort(key=lambda x: x["attendance_percentage"], reverse=True)
	
	return data


def get_attendance_map(filters: Filters) -> dict:
	"""Returns a dictionary of employee wise attendance map as per shifts for all the days of the month like
	{
	    'employee1': {
	            'Morning Shift': {1: 'Present', 2: 'Absent', ...}
	            'Evening Shift': {1: 'Absent', 2: 'Present', ...}
	    },
	    'employee2': {
	            'Afternoon Shift': {1: 'Present', 2: 'Absent', ...}
	            'Night Shift': {1: 'Absent', 2: 'Absent', ...}
	    },
	    'employee3': {
	            None: {1: 'On Leave'}
	    }
	}
	"""
	attendance_list = get_attendance_records(filters)
	attendance_map = {}
	leave_map = {}

	for d in attendance_list:
		if d.status == "On Leave":
			leave_map.setdefault(d.employee, {}).setdefault(d.shift, []).append(d.day_of_month)
			continue

		if d.shift is None:
			d.shift = ""

		attendance_map.setdefault(d.employee, {}).setdefault(d.shift, {})
		attendance_map[d.employee][d.shift][d.day_of_month] = d.status

	# leave is applicable for the entire day so all shifts should show the leave entry
	for employee, leave_days in leave_map.items():
		for assigned_shift, days in leave_days.items():
			# no attendance records exist except leaves
			if employee not in attendance_map:
				attendance_map.setdefault(employee, {}).setdefault(assigned_shift, {})

			for day in days:
				for shift in attendance_map[employee].keys():
					attendance_map[employee][shift][day] = "On Leave"

	return attendance_map


def get_attendance_records(filters: Filters) -> list[dict]:
	"""Modified to handle different date ranges"""
	Attendance = frappe.qb.DocType("Attendance")
	query = (
		frappe.qb.from_(Attendance)
		.select(
			Attendance.employee,
			Extract("day", Attendance.attendance_date).as_("day_of_month"),
			Attendance.status,
			Attendance.shift,
		)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.company.isin(filters.companies))
		)
	)

	if filters.date_range == "Daily":
		query = query.where(Attendance.attendance_date == filters.specific_date)
	elif filters.date_range == "Monthly":
		query = query.where(
			(Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	elif filters.date_range == "Quarterly":
		query = query.where(
			(Extract("month", Attendance.attendance_date).between(filters.from_month, filters.to_month))
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)

	if filters.employee:
		query = query.where(Attendance.employee == filters.employee)
	
	query = query.orderby(Attendance.employee, Attendance.attendance_date)

	return query.run(as_dict=1)


def get_employee_related_details(filters: Filters) -> tuple[dict, list]:
	"""Returns
	1. nested dict for employee details
	2. list of values for the group by filter
	"""
	Employee = frappe.qb.DocType("Employee")
	
	# Define fields to select
	select_fields = [
		Employee.name,
		Employee.employee_name,
		Employee.designation,
		Employee.grade,
		Employee.department,
		Employee.branch,
		Employee.company,
		Employee.holiday_list,
	]
	
	query = (
		frappe.qb.from_(Employee)
		.select(*select_fields)
		.where(Employee.company.isin(filters.companies))
	)

	if filters.employee:
		query = query.where(Employee.name == filters.employee)

	group_by = filters.group_by
	if group_by:
		# Convert group_by to actual field name if needed
		field_mapping = {
			"Branch": "branch",
			"Grade": "grade",
			"Department": "department",
			"Designation": "designation",
			"Route": "custom_route",
			"Area": "custom_area",
			"Zone": "custom_zone",
			"Point": "custom_point"
		}
		
		# Use the base field name for ordering (without 'custom_' prefix)
		order_by = group_by.lower()
		query = query.orderby(order_by)

	employee_details = query.run(as_dict=True)

	group_by_param_values = []
	emp_map = {}

	if group_by:
		# Use the mapped field name for grouping
		field_name = field_mapping.get(group_by)
		group_key = lambda d: "" if d.get(field_name) is None else d.get(field_name)
		
		for parameter, employees in groupby(sorted(employee_details, key=group_key), key=group_key):
			group_by_param_values.append(parameter)
			emp_map.setdefault(parameter, frappe._dict())

			for emp in employees:
				emp_map[parameter][emp.name] = emp
	else:
		for emp in employee_details:
			emp_map[emp.name] = emp

	return emp_map, group_by_param_values


def get_holiday_map(filters: Filters) -> dict[str, list[dict]]:
	"""
	Returns a dict of holidays falling in the filter month and year
	with list name as key and list of holidays as values like
	{
	        'Holiday List 1': [
	                {'day_of_month': '0' , 'weekly_off': 1},
	                {'day_of_month': '1', 'weekly_off': 0}
	        ],
	        'Holiday List 2': [
	                {'day_of_month': '0' , 'weekly_off': 1},
	                {'day_of_month': '1', 'weekly_off': 0}
	        ]
	}
	"""
	# add default holiday list too
	holiday_lists = frappe.db.get_all("Holiday List", pluck="name")
	default_holiday_list = frappe.get_cached_value("Company", filters.company, "default_holiday_list")
	holiday_lists.append(default_holiday_list)

	holiday_map = frappe._dict()
	Holiday = frappe.qb.DocType("Holiday")

	for d in holiday_lists:
		if not d:
			continue

		holidays = (
			frappe.qb.from_(Holiday)
			.select(Extract("day", Holiday.holiday_date).as_("day_of_month"), Holiday.weekly_off)
			.where(
				(Holiday.parent == d)
				& (Extract("month", Holiday.holiday_date) == filters.month)
				& (Extract("year", Holiday.holiday_date) == filters.year)
			)
		).run(as_dict=True)

		holiday_map.setdefault(d, holidays)

	return holiday_map


def get_rows(employee_details: dict, filters: Filters, holiday_map: dict, attendance_map: dict) -> list[dict]:
	records = []
	default_holiday_list = frappe.get_cached_value("Company", filters.company, "default_holiday_list")

	for employee, details in employee_details.items():
		emp_holiday_list = details.holiday_list or default_holiday_list
		holidays = holiday_map.get(emp_holiday_list)

		if filters.summarized_view:
			attendance = get_attendance_status_for_summarized_view(employee, filters, holidays)
			if not attendance:
				continue

			leave_summary = get_leave_summary(employee, filters)
			entry_exits_summary = get_entry_exits_summary(employee, filters)

			row = {"employee": employee, "employee_name": details.employee_name}
			set_defaults_for_summarized_view(filters, row)
			row.update(attendance)
			row.update(leave_summary)
			row.update(entry_exits_summary)

			records.append(row)
		else:
			employee_attendance = attendance_map.get(employee)
			if not employee_attendance:
				continue

			attendance_for_employee = get_attendance_status_for_detailed_view(
				employee, filters, employee_attendance, holidays
			)
			# set employee details in the first row
			attendance_for_employee[0].update({"employee": employee, "employee_name": details.employee_name})

			records.extend(attendance_for_employee)

	return records


def set_defaults_for_summarized_view(filters, row):
	for entry in get_columns(filters):
		if entry.get("fieldtype") == "Float":
			row[entry.get("fieldname")] = 0.0


def get_attendance_status_for_summarized_view(employee: str, filters: Filters, holidays: list) -> dict:
	"""Returns dict of attendance status for employee like
	{'total_present': 1.5, 'total_leaves': 0.5, 'total_absent': 13.5, 'total_holidays': 8, 'unmarked_days': 5}
	"""
	summary, attendance_days = get_attendance_summary_and_days(employee, filters)
	if not any(summary.values()):
		return {}

	total_days = get_total_days_in_month(filters)
	total_holidays = total_unmarked_days = 0

	for day in range(1, total_days + 1):
		if day in attendance_days:
			continue

		status = get_holiday_status(day, holidays)
		if status in ["Weekly Off", "Holiday"]:
			total_holidays += 1
		elif not status:
			total_unmarked_days += 1

	return {
		"total_present": summary.total_present + summary.total_half_days,
		"total_leaves": summary.total_leaves + summary.total_half_days,
		"total_absent": summary.total_absent,
		"total_holidays": total_holidays,
		"unmarked_days": total_unmarked_days,
	}


def get_attendance_summary_and_days(employee: str, filters: Filters) -> tuple[dict, list]:
	Attendance = frappe.qb.DocType("Attendance")

	present_case = (
		frappe.qb.terms.Case()
		.when(((Attendance.status == "Present") | (Attendance.status == "Work From Home")), 1)
		.else_(0)
	)
	sum_present = Sum(present_case).as_("total_present")

	absent_case = frappe.qb.terms.Case().when(Attendance.status == "Absent", 1).else_(0)
	sum_absent = Sum(absent_case).as_("total_absent")

	leave_case = frappe.qb.terms.Case().when(Attendance.status == "On Leave", 1).else_(0)
	sum_leave = Sum(leave_case).as_("total_leaves")

	half_day_case = frappe.qb.terms.Case().when(Attendance.status == "Half Day", 0.5).else_(0)
	sum_half_day = Sum(half_day_case).as_("total_half_days")

	summary = (
		frappe.qb.from_(Attendance)
		.select(
			sum_present,
			sum_absent,
			sum_leave,
			sum_half_day,
		)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company.isin(filters.companies))
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(as_dict=True)

	days = (
		frappe.qb.from_(Attendance)
		.select(Extract("day", Attendance.attendance_date).as_("day_of_month"))
		.distinct()
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company.isin(filters.companies))
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(pluck=True)

	return summary[0], days


def get_attendance_status_for_detailed_view(
	employee: str, filters: Filters, employee_attendance: dict, holidays: list
) -> list[dict]:
	"""Returns list of shift-wise attendance status for employee
	[
	        {'shift': 'Morning Shift', 1: 'A', 2: 'P', 3: 'A'....},
	        {'shift': 'Evening Shift', 1: 'P', 2: 'A', 3: 'P'....}
	]
	"""
	total_days = get_total_days_in_month(filters)
	attendance_values = []

	for shift, status_dict in employee_attendance.items():
		row = {"shift": shift}

		for day in range(1, total_days + 1):
			status = status_dict.get(day)
			if status is None and holidays:
				status = get_holiday_status(day, holidays)

			abbr = status_map.get(status, "")
			row[cstr(day)] = abbr

		attendance_values.append(row)

	return attendance_values


def get_holiday_status(day: int, holidays: list) -> str:
	status = None
	if holidays:
		for holiday in holidays:
			if day == holiday.get("day_of_month"):
				if holiday.get("weekly_off"):
					status = "Weekly Off"
				else:
					status = "Holiday"
				break
	return status


def get_leave_summary(employee: str, filters: Filters) -> dict[str, float]:
	"""Returns a dict of leave type and corresponding leaves taken by employee like:
	{'leave_without_pay': 1.0, 'sick_leave': 2.0}
	"""
	Attendance = frappe.qb.DocType("Attendance")
	day_case = frappe.qb.terms.Case().when(Attendance.status == "Half Day", 0.5).else_(1)
	sum_leave_days = Sum(day_case).as_("leave_days")

	leave_details = (
		frappe.qb.from_(Attendance)
		.select(Attendance.leave_type, sum_leave_days)
		.where(
			(Attendance.employee == employee)
			& (Attendance.docstatus == 1)
			& (Attendance.company.isin(filters.companies))
			& ((Attendance.leave_type.isnotnull()) | (Attendance.leave_type != ""))
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
		.groupby(Attendance.leave_type)
	).run(as_dict=True)

	leaves = {}
	for d in leave_details:
		leave_type = frappe.scrub(d.leave_type)
		leaves[leave_type] = d.leave_days

	return leaves


def get_entry_exits_summary(employee: str, filters: Filters) -> dict[str, float]:
	"""Returns total late entries and total early exits for employee like:
	{'total_late_entries': 5, 'total_early_exits': 2}
	"""
	Attendance = frappe.qb.DocType("Attendance")

	late_entry_case = frappe.qb.terms.Case().when(Attendance.late_entry == "1", "1")
	count_late_entries = Count(late_entry_case).as_("total_late_entries")

	early_exit_case = frappe.qb.terms.Case().when(Attendance.early_exit == "1", "1")
	count_early_exits = Count(early_exit_case).as_("total_early_exits")

	entry_exits = (
		frappe.qb.from_(Attendance)
		.select(count_late_entries, count_early_exits)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company.isin(filters.companies))
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(as_dict=True)

	return entry_exits[0]


@frappe.whitelist()
def get_attendance_years() -> str:
	"""Returns all the years for which attendance records exist"""
	Attendance = frappe.qb.DocType("Attendance")
	year_list = (
		frappe.qb.from_(Attendance).select(Extract("year", Attendance.attendance_date).as_("year")).distinct()
	).run(as_dict=True)

	if year_list:
		year_list.sort(key=lambda d: d.year, reverse=True)
	else:
		year_list = [frappe._dict({"year": getdate().year})]

	return "\n".join(cstr(entry.year) for entry in year_list)


def get_chart_data(attendance_map: dict, filters: Filters) -> dict:
	days = get_columns_for_days(filters)
	labels = []
	absent = []
	present = []
	leave = []

	for day in days:
		labels.append(day["label"])
		total_absent_on_day = total_leaves_on_day = total_present_on_day = 0

		for __, attendance_dict in attendance_map.items():
			for __, attendance in attendance_dict.items():
				attendance_on_day = attendance.get(cint(day["fieldname"]))

				if attendance_on_day == "On Leave":
					# leave should be counted only once for the entire day
					total_leaves_on_day += 1
					break
				elif attendance_on_day == "Absent":
					total_absent_on_day += 1
				elif attendance_on_day in ["Present", "Work From Home"]:
					total_present_on_day += 1
				elif attendance_on_day == "Half Day":
					total_present_on_day += 0.5
					total_leaves_on_day += 0.5

		absent.append(total_absent_on_day)
		present.append(total_present_on_day)
		leave.append(total_leaves_on_day)

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": "Absent", "values": absent},
				{"name": "Present", "values": present},
				{"name": "Leave", "values": leave},
			],
		},
		"type": "line",
		"colors": ["red", "green", "blue"],
	}


def get_columns_for_days(filters: Filters) -> list[dict]:
	"""Returns list of dict containing column definitions for each day of the month/quarter"""
	days = []

	if filters.date_range == "Daily":
		# For daily view, only show one day
		day = getdate(filters.specific_date).day
		weekday = day_abbr[getdate(filters.specific_date).weekday()]
		label = f"{day} {weekday}"
		days.append({"label": label, "fieldtype": "Data", "fieldname": str(day), "width": 65})
	
	elif filters.date_range == "Monthly":
		total_days = get_total_days_in_month(filters)
		for day in range(1, total_days + 1):
			date = f"{cstr(filters.year)}-{cstr(filters.month)}-{cstr(day)}"
			weekday = day_abbr[getdate(date).weekday()]
			label = f"{day} {weekday}"
			days.append({"label": label, "fieldtype": "Data", "fieldname": str(day), "width": 65})
	
	elif filters.date_range == "Quarterly":
		# For quarterly view, show month names instead of days
		for month in range(filters.from_month, filters.to_month + 1):
			month_name = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
						 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month - 1]
			days.append({"label": month_name, "fieldtype": "Data", "fieldname": str(month), "width": 100})

	return days


def get_total_days_in_month(filters: Filters) -> int:
	"""Returns total number of days in the selected month"""
	return monthrange(cint(filters.year), cint(filters.month))[1]


def get_message() -> str:
	"""Returns formatted message with status indicators"""
	message = ""
	colors = ["green", "red", "orange", "green", "#318AD8", "", ""]

	count = 0
	for status, abbr in status_map.items():
		message += f"""
			<span style='border-left: 2px solid {colors[count]}; padding-right: 12px; padding-left: 5px; margin-right: 3px;'>
				{status} - {abbr}
			</span>
		"""
		count += 1

	return message
