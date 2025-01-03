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

    # Initialize chart at the start
    chart = {
        "data": {
            "labels": ["Present", "Absent", "On Leave"],
            "datasets": [{"name": "Attendance Distribution", "values": [0, 0, 0]}]
        },
        "type": "pie",
        "colors": ["#36a2eb", "#ff6384", "#ffcd56"],
        "height": 280
    }

    # Handle case when no data is found
    if not data:
        message = "No employees found for the selected criteria."
        report_summary = [
            {"value": 0, "label": "Total Employees", "datatype": "Int", "indicator": "gray"},
            {"value": 0, "label": "Present", "datatype": "Int", "indicator": "gray"},
            {"value": 0, "label": "Absent", "datatype": "Int", "indicator": "gray"},
            {"value": 0, "label": "On Leave", "datatype": "Int", "indicator": "gray"},
            {"value": 0, "label": "Attendance %", "datatype": "Percent", "indicator": "gray"}
        ]
        return columns, [], message, chart, report_summary

    # Calculate totals from grand total row
    grand_total_row = data[-1] if data else {}
    total_employees = grand_total_row.get("total_employees", 0)
    total_present = grand_total_row.get("present", 0)
    total_absent = grand_total_row.get("absent", 0)
    total_on_leave = grand_total_row.get("on_leave", 0)
    total_marked = total_present + total_absent + total_on_leave

    # Get all unique designations with employee counts
    designation_data = frappe.get_all(
        "Employee",
        fields=["designation", "count(*) as total"],
        filters={
            "company": ("in", filters.companies),
            "status": "Active",
            "custom_point": ("in", [row["point"] for row in data if row.get("point")])
        },
        group_by="designation",
        order_by="designation"
    )

    # Handle case when no attendance records found
    if total_marked == 0:
        base_message = f"No attendance records found for {filters.date}.\n\n"
        if total_employees > 0:
            base_message += f"Total Employees: {total_employees}\n\nDesignation-wise Employee Count:"
            for d in designation_data:
                base_message += f"\n{d.designation}: {d.total} employees"
        return columns, data, base_message, chart, report_summary

    # Calculate percentages for normal case
    overall_attendance_percentage = (total_present / total_marked * 100) if total_marked else 0
    present_percentage = f"{(total_present/total_marked*100):.1f}" if total_marked else "0.0"
    absent_percentage = f"{(total_absent/total_marked*100):.1f}" if total_marked else "0.0"
    leave_percentage = f"{(total_on_leave/total_marked*100):.1f}" if total_marked else "0.0"

    # Create the main message with HTML formatting
    message = [
        "<div style='font-family: Arial; padding: 10px;'>",
        "<h3 style='color: #1F497D; margin-bottom: 15px;'>Overall Attendance Summary</h3>",
        f"<div style='margin-bottom: 15px;'><b>Total Employees:</b> {total_employees}</div>",
        f"<div style='margin-bottom: 15px;'><b>Overall Attendance:</b> {overall_attendance_percentage:.1f}%</div>",
        "<div style='margin-bottom: 15px;'>",
        "<b>Attendance Breakdown:</b>",
        f"<div style='margin-left: 20px; margin-top: 5px;'>• Present: <b>{total_present}</b> ({present_percentage}%)</div>",
        f"<div style='margin-left: 20px;'>• Absent: <b>{total_absent}</b> ({absent_percentage}%)</div>",
        f"<div style='margin-left: 20px;'>• On Leave: <b>{total_on_leave}</b> ({leave_percentage}%)</div>",
        "</div>",
        "<div style='margin-top: 20px;'>",
        "<h3 style='color: #1F497D; margin-bottom: 15px;'>Designation-wise Breakdown</h3>",
        "<div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px;'>"
    ]
    
    for desig in designation_data:
        # Get attendance for this designation
        attendance = frappe.get_all(
            "Attendance",
            fields=["status", "count(*) as count"],
            filters={
                "attendance_date": filters.date,
                "docstatus": 1,
                "employee": ("in", 
                    frappe.get_all(
                        "Employee",
                        filters={
                            "designation": desig.designation,
                            "company": ("in", filters.companies),
                            "status": "Active",
                            "custom_point": ("in", [row["point"] for row in data if row.get("point")])
                        },
                        pluck="name"
                    )
                )
            },
            group_by="status"
        )

        # Calculate attendance counts and percentages
        present = sum(a.count for a in attendance if a.status in ["Present", "Work From Home"])
        absent = sum(a.count for a in attendance if a.status == "Absent")
        on_leave = sum(a.count for a in attendance if a.status == "On Leave")
        marked = present + absent + on_leave
        
        if marked > 0:
            present_pct = (present / marked * 100)
            absent_pct = (absent / marked * 100)
            leave_pct = (on_leave / marked * 100)
        else:
            present_pct = absent_pct = leave_pct = 0

        message.append(
            f"""<div style='padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px;'>
                <div style='font-weight: bold; color: #4472C4; margin-bottom: 5px;'>{desig.designation}</div>
                <div style='color: #666; font-size: 0.9em; margin-bottom: 10px;'>({desig.total} employees)</div>
                <div style='margin-bottom: 3px;'>Present: <b>{present}</b> ({present_pct:.1f}%)</div>
                <div style='margin-bottom: 3px;'>Absent: <b>{absent}</b> ({absent_pct:.1f}%)</div>
                <div>On Leave: <b>{on_leave}</b> ({leave_pct:.1f}%)</div>
            </div>"""
        )

    message.extend(["</div>", "</div>", "</div>"])
    message = "".join(message)

    # Create chart
    chart = {
        "data": {
            "labels": ["Present", "Absent", "On Leave"],
            "datasets": [{
                "name": "Attendance Distribution",
                "values": [total_present, total_absent, total_on_leave]
            }]
        },
        "type": "pie",
        "colors": ["#36a2eb", "#ff6384", "#ffcd56"],
        "height": 280
    }

    # Create report summary
    report_summary = [
        {"value": total_employees, "label": "Total Employees", "datatype": "Int", "indicator": "gray"},
        {"value": total_present, "label": "Present", "datatype": "Int", "indicator": "green"},
        {"value": total_absent, "label": "Absent", "datatype": "Int", "indicator": "red"},
        {"value": total_on_leave, "label": "On Leave", "datatype": "Int", "indicator": "yellow"},
        {"value": overall_attendance_percentage, "label": "Attendance %", "datatype": "Percent", "indicator": "blue"}
    ]

    return columns, data, message, chart, report_summary

def get_columns():
    return [
        {
            "label": _("Zone"),
            "fieldname": "zone",
            "fieldtype": "Link",
            "options": "Zone",
            "width": 150
        },
        {
            "label": _("Point"),
            "fieldname": "point",
            "fieldtype": "Link",
            "options": "Point",
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
    # First get allowed points based on permissions and filters
    point_filters = {"is_active": 1}
    
    # Add zone filter if specified
    if filters.get("zones"):
        point_filters["zone_name"] = ("in", filters.get("zones"))
    
    allowed_points = frappe.get_list("Point", 
        fields=["name", "zone_name"],
        filters=point_filters
    )
    
    # Create point to zone mapping
    point_zone_map = {p.name: p.zone_name for p in allowed_points}
    
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
    zone_wise_data = {}  # For grouping by zone

    for point_data in points:
        if not point_data.point:
            continue

        # Get zone for this point
        zone = point_zone_map.get(point_data.point, "")

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

        row_data = {
            "zone": zone,
            "point": point_data.point,
            "total_employees": point_data.total_employees,
            "present": present,
            "absent": absent,
            "on_leave": on_leave,
            "attendance_percentage": attendance_percentage
        }

        data.append(row_data)

        # Aggregate zone-wise data
        if zone not in zone_wise_data:
            zone_wise_data[zone] = {
                "total_employees": 0,
                "present": 0,
                "absent": 0,
                "on_leave": 0
            }
        zone_wise_data[zone]["total_employees"] += point_data.total_employees
        zone_wise_data[zone]["present"] += present
        zone_wise_data[zone]["absent"] += absent
        zone_wise_data[zone]["on_leave"] += on_leave

    # Sort by zone and then attendance percentage
    data.sort(key=lambda x: (x["zone"] or "", x["attendance_percentage"]), reverse=True)

    # Add zone subtotals (commented out)
    final_data = []
    current_zone = None
    for row in data:
        # if row["zone"] != current_zone:
        #     if current_zone is not None:
        #         # Add zone total
        #         zone_total = zone_wise_data[current_zone]
        #         zone_marked = zone_total["present"] + zone_total["absent"] + zone_total["on_leave"]
        #         final_data.append({
        #             "zone": current_zone + " Total",
        #             "point": "",
        #             "total_employees": zone_total["total_employees"],
        #             "present": zone_total["present"],
        #             "absent": zone_total["absent"],
        #             "on_leave": zone_total["on_leave"],
        #             "attendance_percentage": (zone_total["present"] / zone_marked * 100) if zone_marked else 0
        #         })
        #     current_zone = row["zone"]
        final_data.append(row)

    # Add last zone total if exists (commented out)
    # if current_zone:
    #     zone_total = zone_wise_data[current_zone]
    #     zone_marked = zone_total["present"] + zone_total["absent"] + zone_total["on_leave"]
    #     final_data.append({
    #         "zone": current_zone + " Total",
    #         "point": "",
    #         "total_employees": zone_total["total_employees"],
    #         "present": zone_total["present"],
    #         "absent": zone_total["absent"],
    #         "on_leave": zone_total["on_leave"],
    #         "attendance_percentage": (zone_total["present"] / zone_marked * 100) if zone_marked else 0
    #     })

    # Add grand total
    total_employees = sum(row["total_employees"] for row in data)
    total_present = sum(row["present"] for row in data)
    total_absent = sum(row["absent"] for row in data)
    total_on_leave = sum(row["on_leave"] for row in data)
    total_marked = total_present + total_absent + total_on_leave
    
    final_data.append({
        "zone": "Grand Total",
        "point": "",
        "total_employees": total_employees,
        "present": total_present,
        "absent": total_absent,
        "on_leave": total_on_leave,
        "attendance_percentage": (total_present / total_marked * 100) if total_marked else 0
    })

    return final_data