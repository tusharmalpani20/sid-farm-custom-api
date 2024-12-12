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
    data = get_point_wise_attendance(filters)

    # Calculate totals for summary and chart
    total_employees = sum(row["total_employees"] for row in data[:-1])  # Exclude the total row
    total_present = sum(row["present"] for row in data[:-1])
    total_absent = sum(row["absent"] for row in data[:-1])
    total_on_leave = sum(row["on_leave"] for row in data[:-1])
    total_marked = total_present + total_absent + total_on_leave
    overall_attendance_percentage = (total_present / total_marked * 100) if total_marked else 0

    # Create report summary (shown at top)
    report_summary = [
        {
            "value": total_employees,
            "label": "Total Employees",
            "datatype": "Int",
            "indicator": "blue"
        },
        {
            "value": total_present,
            "label": "Present",
            "datatype": "Int",
            "indicator": "green"
        },
        {
            "value": total_absent,
            "label": "Absent",
            "datatype": "Int",
            "indicator": "red"
        },
        {
            "value": total_on_leave,
            "label": "On Leave",
            "datatype": "Int",
            "indicator": "orange"
        },
        {
            "value": overall_attendance_percentage,
            "label": "Attendance %",
            "datatype": "Percent",
            "indicator": "blue"
        }
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
        "colors": ["#28a745", "#dc3545", "#ffc107"],  # Green, Red, Yellow
        "height": 280
    }

    return columns, data, report_summary, chart

def get_columns():
    return [
        {
            "label": _("Point"),
            "fieldname": "point",
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

def get_point_wise_attendance(filters):
    # First get allowed points based on permissions
    allowed_points = frappe.get_list("Point", 
        fields=["name"],
        filters={"is_active": 1}
    )
    
    # Get all points and their employees
    point_filters = {
        "company": ("in", filters.companies),
        "status": "Active",
        "custom_point": ("in", [p.name for p in allowed_points])
    }
    
    # Add points filter if specified
    if filters.get("points"):
        point_filters["custom_point"] = ("in", [
            p for p in filters.get("points") 
            if p in [ap.name for ap in allowed_points]
        ])

    points = frappe.get_all(
        "Employee",
        fields=[
            "custom_point as point",
            "count(*) as total_employees"
        ],
        filters=point_filters,
        group_by="custom_point"
    )

    data = []
    for point_data in points:
        if not point_data.point:
            continue

        # Get employees for this point
        point_employees = frappe.get_all(
            "Employee",
            fields=["name"],
            filters={
                "custom_point": point_data.point,
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
                "employee": ("in", [emp.name for emp in point_employees]),
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
            "point": point_data.point,
            "total_employees": point_data.total_employees,
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
        "point": "Total",
        "total_employees": total_employees,
        "present": total_present,
        "absent": total_absent,
        "on_leave": total_on_leave,
        "attendance_percentage": overall_attendance_percentage
    })

    return data
