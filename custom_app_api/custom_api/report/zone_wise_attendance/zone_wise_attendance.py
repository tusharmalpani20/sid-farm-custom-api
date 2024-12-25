import frappe
from frappe import _
from frappe.utils.nestedset import get_descendants_of

def execute(filters=None):
    if not filters:
        filters = {}

    if filters.get("company"):
        filters.companies = [filters.get("company")]
        if filters.get("include_company_descendants"):
            filters.companies.extend(get_descendants_of("Company", filters.get("company")))

    columns = get_columns()
    data = get_zone_wise_attendance(filters)

    # Calculate totals for summary and chart
    total_employees = sum(row["total_employees"] for row in data[:-1])  # Exclude the last (Total) row
    total_present = sum(row["present"] for row in data[:-1])
    total_absent = sum(row["absent"] for row in data[:-1])
    total_on_leave = sum(row["on_leave"] for row in data[:-1])
    total_marked = total_present + total_absent + total_on_leave

    # Handle case when there's no attendance data
    if total_marked == 0:
        message = ["No attendance records found for the selected date."]
        # Create empty chart
        chart = {
            "data": {
                "labels": ["Present", "Absent", "On Leave"],
                "datasets": [{"name": "Attendance Distribution", "values": [0, 0, 0]}]
            },
            "type": "pie",
            "colors": ["#28a745", "#dc3545", "#ffc107"],
            "height": 280
        }
        # Create empty summary
        report_summary = [
            {
                "value": total_employees,
                "label": "Total Employees",
                "datatype": "Int",
                "indicator": "gray"
            },
            {
                "value": 0,
                "label": "Present",
                "datatype": "Int",
                "indicator": "gray"
            },
            {
                "value": 0,
                "label": "Absent",
                "datatype": "Int",
                "indicator": "gray"
            },
            {
                "value": 0,
                "label": "On Leave",
                "datatype": "Int",
                "indicator": "gray"
            },
            {
                "value": 0,
                "label": "Attendance %",
                "datatype": "Percent",
                "indicator": "gray"
            }
        ]
    else:
        overall_attendance_percentage = (total_present / total_marked * 100) if total_marked else 0
        
        # Calculate percentages safely
        present_percentage = f"{(total_present/total_marked*100):.1f}" if total_marked else "0.0"
        absent_percentage = f"{(total_absent/total_marked*100):.1f}" if total_marked else "0.0"
        leave_percentage = f"{(total_on_leave/total_marked*100):.1f}" if total_marked else "0.0"

        message = [
            f"Total Employees: {total_employees}",
            f"Overall Attendance: {overall_attendance_percentage:.1f}%",
            f"Present: {total_present} ({present_percentage}%)",
            f"Absent: {total_absent} ({absent_percentage}%)",
            f"On Leave: {total_on_leave} ({leave_percentage}%)"
        ]

        # Create pie chart
        chart = {
            "data": {
                "labels": ["Present", "Absent", "On Leave"],
                "datasets": [{
                    "name": "Attendance Distribution",
                    "values": [total_present, total_absent, total_on_leave]
                }]
            },
            "type": "pie",
            "colors": ["#36a2eb", "#ff6384", "#ffcd56"],  # Professional blue, soft red, muted yellow
            "height": 280
        }

        # Create report summary with indicators
        report_summary = [
            {
                "value": total_employees,
                "label": "Total Employees",
                "datatype": "Int",
                "indicator": "gray"
            },
            {
                "value": total_present,
                "label": "Present",
                "datatype": "Int",
                "indicator": "gray"
            },
            {
                "value": total_absent,
                "label": "Absent",
                "datatype": "Int",
                "indicator": "gray"
            },
            {
                "value": total_on_leave,
                "label": "On Leave",
                "datatype": "Int",
                "indicator": "gray"
            },
            {
                "value": overall_attendance_percentage,
                "label": "Attendance %",
                "datatype": "Percent",
                "indicator": "gray"
            }
        ]

    return columns, data, None, chart, report_summary

def get_columns():
    return [
        {
            "label": _("Zone"),
            "fieldname": "zone",
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
            "fieldname": "present",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Absent"),
            "fieldname": "absent",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("On Leave"),
            "fieldname": "on_leave",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Attendance %"),
            "fieldname": "attendance_percentage",
            "fieldtype": "Percent",
            "width": 100
        }
    ]

def get_zone_wise_attendance(filters):
    # First get all zones (removed is_active filter since the column doesn't exist)
    allowed_zones = frappe.get_list("Zone", 
        fields=["name"]
    )
    
    # Get all zones and their employees
    zone_filters = {
        "company": ("in", filters.companies),
        "status": "Active",
        "custom_zone": ("in", [z.name for z in allowed_zones])
    }
    
    # Add zones filter if specified
    if filters.get("zones"):
        zone_filters["custom_zone"] = ("in", [
            z for z in filters.get("zones")
            if z in [az.name for az in allowed_zones]
        ])

    zones = frappe.get_all(
        "Employee",
        fields=[
            "custom_zone as zone",
            "count(*) as total_employees"
        ],
        filters=zone_filters,
        group_by="custom_zone"
    )

    data = []
    for zone_data in zones:
        if not zone_data.zone:
            continue

        # Get employees for this zone
        zone_employees = frappe.get_all(
            "Employee",
            fields=["name"],
            filters={
                "custom_zone": zone_data.zone,
                "company": ("in", filters.companies),
                "status": "Active"
            }
        )

        # Get attendance for these employees
        attendance_counts = frappe.get_all(
            "Attendance",
            fields=[
                "status",
                "count(*) as count"
            ],
            filters={
                "attendance_date": filters.date,
                "employee": ("in", [emp.name for emp in zone_employees]),
                "docstatus": 1
            },
            group_by="status"
        )

        # Initialize counters
        present = absent = on_leave = 0

        # Process attendance counts
        for count_data in attendance_counts:
            if count_data.status in ["Present", "Work From Home"]:
                present = count_data.count
            elif count_data.status == "Absent":
                absent = count_data.count
            elif count_data.status == "On Leave":
                on_leave = count_data.count

        # Calculate attendance percentage
        total_marked = present + absent + on_leave
        attendance_percentage = (present / total_marked * 100) if total_marked else 0

        data.append({
            "zone": zone_data.zone,
            "total_employees": zone_data.total_employees,
            "present": present,
            "absent": absent,
            "on_leave": on_leave,
            "attendance_percentage": attendance_percentage
        })

    # Sort by attendance percentage in descending order
    data.sort(key=lambda x: x["attendance_percentage"], reverse=True)

    # Calculate totals
    total_employees = sum(row["total_employees"] for row in data)
    total_present = sum(row["present"] for row in data)
    total_absent = sum(row["absent"] for row in data)
    total_on_leave = sum(row["on_leave"] for row in data)
    total_marked = total_present + total_absent + total_on_leave
    overall_attendance_percentage = (total_present / total_marked * 100) if total_marked else 0

    # Add totals row
    data.append({
        "zone": "<b>Total</b>",
        "total_employees": total_employees,
        "present": total_present,
        "absent": total_absent,
        "on_leave": total_on_leave,
        "attendance_percentage": overall_attendance_percentage
    })

    return data
