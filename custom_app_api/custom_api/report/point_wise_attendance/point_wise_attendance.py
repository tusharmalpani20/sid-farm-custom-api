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
        #return columns, [], message, chart, report_summary
        return columns, [], message, None, None


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
        # return columns, data, base_message, chart, report_summary
        return columns, data, base_message, None, None

    # Calculate percentages for normal case
    overall_attendance_percentage = (total_present / total_marked * 100) if total_marked else 0
    present_percentage = f"{(total_present/total_marked*100):.1f}" if total_marked else "0.0"
    absent_percentage = f"{(total_absent/total_marked*100):.1f}" if total_marked else "0.0"
    leave_percentage = f"{(total_on_leave/total_marked*100):.1f}" if total_marked else "0.0"

    # Create the main message with modern HTML formatting
    message = [
        "<div style='font-family: system-ui, -apple-system, sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto;'>",
        "<div style='background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);'>",
        "<h2 style='color: #2c3e50; margin-bottom: 24px; font-weight: 600;'>Overall Attendance Summary</h2>",
        
        # Stats cards container
        "<div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;'>",
        
        # Total Employees Card
        f"<div style='background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;'>"
        f"<div style='color: #64748b; font-size: 0.875rem; margin-bottom: 4px;'>Total Employees</div>"
        f"<div style='color: #1e293b; font-size: 1.5rem; font-weight: 600;'>{total_employees}</div>"
        "</div>",
        
        # Overall Attendance Card
        f"<div style='background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;'>"
        f"<div style='color: #64748b; font-size: 0.875rem; margin-bottom: 4px;'>Overall Attendance</div>"
        f"<div style='color: #1e293b; font-size: 1.5rem; font-weight: 600;'>{overall_attendance_percentage:.1f}%</div>"
        "</div>",
        "</div>",
        
        # Attendance Breakdown Section
        "<div style='background: #f8fafc; border-radius: 8px; padding: 20px; margin-bottom: 32px; border: 1px solid #e2e8f0;'>",
        "<h3 style='color: #2c3e50; margin-bottom: 16px; font-size: 1.1rem; font-weight: 600;'>Attendance Breakdown</h3>",
        "<div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px;'>",
        
        # Present Stats
        f"<div style='padding: 12px; background: #dcfce7; border-radius: 6px;'>"
        f"<div style='color: #166534; font-size: 0.875rem;'>Present</div>"
        f"<div style='font-weight: 600; color: #166534; font-size: 1.25rem;'>{total_present}</div>"
        f"<div style='color: #166534; font-size: 0.875rem;'>({present_percentage}%)</div>"
        "</div>",
        
        # Absent Stats
        f"<div style='padding: 12px; background: #fee2e2; border-radius: 6px;'>"
        f"<div style='color: #991b1b; font-size: 0.875rem;'>Absent</div>"
        f"<div style='font-weight: 600; color: #991b1b; font-size: 1.25rem;'>{total_absent}</div>"
        f"<div style='color: #991b1b; font-size: 0.875rem;'>({absent_percentage}%)</div>"
        "</div>",
        
        # On Leave Stats
        f"<div style='padding: 12px; background: #fef3c7; border-radius: 6px;'>"
        f"<div style='color: #92400e; font-size: 0.875rem;'>On Leave</div>"
        f"<div style='font-weight: 600; color: #92400e; font-size: 1.25rem;'>{total_on_leave}</div>"
        f"<div style='color: #92400e; font-size: 0.875rem;'>({leave_percentage}%)</div>"
        "</div>",
        "</div>", # End of breakdown grid
        "</div>", # End of breakdown section
        
        # Designation-wise Section
        "<h2 style='color: #2c3e50; margin-bottom: 24px; font-weight: 600;'>Designation-wise Breakdown</h2>",
        "<div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;'>"
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
            f"""<div style='background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;'>
                    <div style='font-weight: 600; color: #2c3e50; font-size: 1.1rem;'>{desig.designation}</div>
                    <div style='color: #64748b; font-size: 0.875rem; padding: 4px 12px; background: #f1f5f9; border-radius: 12px;'>{desig.total} employees</div>
                </div>
                <div style='display: grid; gap: 12px;'>
                    <div style='display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;'>
                        <span style='color: #16a34a;'>Present</span>
                        <span style='font-weight: 500;'>{present} ({present_pct:.1f}%)</span>
                    </div>
                    <div style='display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;'>
                        <span style='color: #dc2626;'>Absent</span>
                        <span style='font-weight: 500;'>{absent} ({absent_pct:.1f}%)</span>
                    </div>
                    <div style='display: flex; justify-content: space-between; padding: 8px 0;'>
                        <span style='color: #d97706;'>On Leave</span>
                        <span style='font-weight: 500;'>{on_leave} ({leave_pct:.1f}%)</span>
                    </div>
                </div>
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

    # return columns, data, message, chart, report_summary
    return columns, data, message, None, None

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
            "label": _("Designation"),
            "fieldname": "designation",
            "fieldtype": "Link",
            "options": "Designation",
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
    point_designation_data = {}  # For storing designation data by point

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

        # Get designation-wise data for this point
        designations = frappe.get_all(
            "Employee",
            fields=["designation", "count(*) as total_employees"],
            filters={
                "custom_point": point_data.point,
                "company": ("in", filters.companies),
                "status": "Active"
            },
            group_by="designation",
            order_by="designation"
        )

        # Add the point summary row first
        row_data = {
            "zone": zone,
            "point": point_data.point,
            "designation": "",  # Empty for the point summary row
            "total_employees": point_data.total_employees,
            "present": present,
            "absent": absent,
            "on_leave": on_leave,
            "attendance_percentage": attendance_percentage,
            "is_point_total": 1  # Flag to identify point total rows
        }
        data.append(row_data)

        # Add designation-wise rows for this point
        for desig in designations:
            # Get employees for this designation at this point
            desig_employees = frappe.get_all(
                "Employee",
                fields=["name"],
                filters={
                    "custom_point": point_data.point,
                    "designation": desig.designation,
                    "company": ("in", filters.companies),
                    "status": "Active"
                }
            )

            # Get attendance for these employees
            desig_attendance = frappe.get_all(
                "Attendance",
                fields=[
                    "status",
                    "count(*) as count"
                ],
                filters={
                    "attendance_date": filters.date,
                    "employee": ("in", [emp.name for emp in desig_employees]),
                    "docstatus": 1
                },
                group_by="status"
            )

            # Initialize counters for this designation
            desig_present = desig_absent = desig_on_leave = 0

            # Process attendance counts for this designation
            for count_data in desig_attendance:
                if count_data.status in ["Present", "Work From Home"]:
                    desig_present = count_data.count
                elif count_data.status == "Absent":
                    desig_absent = count_data.count
                elif count_data.status == "On Leave":
                    desig_on_leave = count_data.count

            # Calculate attendance percentage for this designation
            desig_total_marked = desig_present + desig_absent + desig_on_leave
            desig_attendance_percentage = (desig_present / desig_total_marked * 100) if desig_total_marked else 0

            # Add designation row
            desig_row = {
                "zone": "",  # Empty for designation rows
                "point": "",  # Empty for designation rows
                "designation": desig.designation,
                "total_employees": desig.total_employees,
                "present": desig_present,
                "absent": desig_absent,
                "on_leave": desig_on_leave,
                "attendance_percentage": desig_attendance_percentage,
                "indent": 1  # Indent to show hierarchy
            }
            data.append(desig_row)

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

    # Sort by zone and then attendance percentage for point totals
    # We need to preserve the grouping of designations under their points
    sorted_data = []
    points_by_zone = {}
    
    # Group points by zone
    for row in data:
        if row.get("is_point_total"):
            zone = row["zone"] or ""
            if zone not in points_by_zone:
                points_by_zone[zone] = []
            points_by_zone[zone].append(row)
    
    # Sort zones
    for zone in sorted(points_by_zone.keys()):
        # Sort points within zone by attendance percentage
        points = sorted(points_by_zone[zone], key=lambda x: x["attendance_percentage"], reverse=True)
        
        for point_row in points:
            # Add the point row
            sorted_data.append(point_row)
            
            # Add all designation rows for this point
            point_designations = [r for r in data if r.get("indent") and not r.get("zone") and r.get("designation") and not r.get("point")]
            point_designations.sort(key=lambda x: x["designation"])
            sorted_data.extend(point_designations)

    # Add grand total
    total_employees = sum(row["total_employees"] for row in data if row.get("is_point_total", 0))
    total_present = sum(row["present"] for row in data if row.get("is_point_total", 0))
    total_absent = sum(row["absent"] for row in data if row.get("is_point_total", 0))
    total_on_leave = sum(row["on_leave"] for row in data if row.get("is_point_total", 0))
    total_marked = total_present + total_absent + total_on_leave
    
    sorted_data.append({
        "zone": "Grand Total",
        "point": "",
        "designation": "",
        "total_employees": total_employees,
        "present": total_present,
        "absent": total_absent,
        "on_leave": total_on_leave,
        "attendance_percentage": (total_present / total_marked * 100) if total_marked else 0
    })

    return sorted_data