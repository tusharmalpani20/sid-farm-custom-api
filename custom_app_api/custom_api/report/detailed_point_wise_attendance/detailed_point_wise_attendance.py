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
    # First get all unique designations
    designations = frappe.get_all(
        "Employee",
        fields=["designation"],
        filters={"status": "Active"},
        distinct=True,
        order_by="designation"
    )

    columns = [
        {
            "label": _("Point"),
            "fieldname": "point",
            "fieldtype": "Data",
            "width": 200
        }
    ]

    # Add columns for each designation
    for designation in designations:
        designation_key = designation.designation.replace(" ", "_").lower()
        
        # Total column for this designation
        columns.append({
            "label": _(f"Total {designation.designation}"),
            "fieldname": f"total_{designation_key}",
            "fieldtype": "Int",
            "width": 100
        })
        # Present column for this designation
        columns.append({
            "label": _(f"Present {designation.designation}"),
            "fieldname": f"present_{designation_key}",
            "fieldtype": "Int",
            "width": 100
        })
        # Absent column for this designation
        columns.append({
            "label": _(f"Absent {designation.designation}"),
            "fieldname": f"absent_{designation_key}",
            "fieldtype": "Int",
            "width": 100
        })
        # On Leave column for this designation
        columns.append({
            "label": _(f"On Leave {designation.designation}"),
            "fieldname": f"on_leave_{designation_key}",
            "fieldtype": "Int",
            "width": 100
        })
        # Attendance % column for this designation
        columns.append({
            "label": _(f"Attendance % {designation.designation}"),
            "fieldname": f"attendance_percentage_{designation_key}",
            "fieldtype": "Percent",
            "width": 100
        })

    # Add total columns at the end
    columns.extend([
        {
            "label": _("Total Employees"),
            "fieldname": "total_employees",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Total Present"),
            "fieldname": "present",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Total Absent"),
            "fieldname": "absent",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Total On Leave"),
            "fieldname": "on_leave",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Overall Attendance %"),
            "fieldname": "attendance_percentage",
            "fieldtype": "Percent",
            "width": 100
        }
    ])

    return columns

def get_point_wise_attendance(filters):
    # Get allowed points
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
    
    if filters.get("points"):
        point_filters["custom_point"] = ("in", [
            p for p in filters.get("points") 
            if p in [ap.name for ap in allowed_points]
        ])

    # Get all unique designations
    designations = frappe.get_all(
        "Employee",
        fields=["designation"],
        filters={"status": "Active"},
        distinct=True
    )

    data = []
    points = frappe.get_all(
        "Employee",
        fields=[
            "custom_point as point",
            "count(*) as total_employees"
        ],
        filters=point_filters,
        group_by="custom_point"
    )

    for point_data in points:
        if not point_data.point:
            continue

        row_data = {"point": point_data.point}
        total_present = total_absent = total_on_leave = 0

        # Process each designation
        for designation in designations:
            designation_key = designation.designation.replace(" ", "_").lower()

            # Get employees for this point and designation
            point_employees = frappe.get_all(
                "Employee",
                fields=["name"],
                filters={
                    "custom_point": point_data.point,
                    "company": ("in", filters.companies),
                    "status": "Active",
                    "designation": designation.designation
                }
            )

            # Get total employees for this designation
            row_data[f"total_{designation_key}"] = len(point_employees)

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

            # Initialize counters for this designation
            present = absent = on_leave = 0

            # Process attendance counts
            for count_data in attendance_counts:
                if count_data.status in ["Present", "Work From Home"]:
                    present = count_data.count
                elif count_data.status == "Absent":
                    absent = count_data.count
                elif count_data.status == "On Leave":
                    on_leave = count_data.count

            # Update designation-specific fields
            row_data[f"present_{designation_key}"] = present
            row_data[f"absent_{designation_key}"] = absent
            row_data[f"on_leave_{designation_key}"] = on_leave
            
            # Calculate attendance percentage for this designation
            total_emp_designation = row_data[f"total_{designation_key}"]
            row_data[f"attendance_percentage_{designation_key}"] = (
                (present / total_emp_designation * 100) if total_emp_designation else 0
            )

            # Add to totals
            total_present += present
            total_absent += absent
            total_on_leave += on_leave

        # Add overall totals
        row_data.update({
            "total_employees": point_data.total_employees,
            "present": total_present,
            "absent": total_absent,
            "on_leave": total_on_leave,
            "attendance_percentage": (
                (total_present / point_data.total_employees * 100) 
                if point_data.total_employees else 0
            )
        })

        data.append(row_data)

    # Sort by overall attendance percentage
    data.sort(key=lambda x: x["attendance_percentage"], reverse=True)

    # Calculate grand totals
    grand_totals = {"point": "<b>Total</b>"}
    
    # Initialize grand totals for each designation
    for designation in designations:
        designation_key = designation.designation.replace(" ", "_").lower()
        grand_totals[f"total_{designation_key}"] = sum(row[f"total_{designation_key}"] for row in data)
        grand_totals[f"present_{designation_key}"] = sum(row[f"present_{designation_key}"] for row in data)
        grand_totals[f"absent_{designation_key}"] = sum(row[f"absent_{designation_key}"] for row in data)
        grand_totals[f"on_leave_{designation_key}"] = sum(row[f"on_leave_{designation_key}"] for row in data)
        
        total_emp_designation = grand_totals[f"total_{designation_key}"]
        grand_totals[f"attendance_percentage_{designation_key}"] = (
            (grand_totals[f"present_{designation_key}"] / total_emp_designation * 100)
            if total_emp_designation else 0
        )

    # Add overall totals
    grand_totals.update({
        "total_employees": sum(row["total_employees"] for row in data),
        "present": sum(row["present"] for row in data),
        "absent": sum(row["absent"] for row in data),
        "on_leave": sum(row["on_leave"] for row in data)
    })
    
    grand_totals["attendance_percentage"] = (
        (grand_totals["present"] / grand_totals["total_employees"] * 100)
        if grand_totals["total_employees"] else 0
    )

    data.append(grand_totals)
    return data
