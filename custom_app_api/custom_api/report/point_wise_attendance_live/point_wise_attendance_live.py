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

    if not data:
        message = "No employees found for the selected criteria."
        return columns, [], message, None, None

    # Create summary message
    status_counts = {
        "Present": len([d for d in data if d["status"] in ["Present", "Work From Home"]]),
        "Absent": len([d for d in data if d["status"] == "Absent"]),
        "On Leave": len([d for d in data if d["status"] == "On Leave"]),
        "Not Marked": len([d for d in data if d["status"] == "Not Marked"])
    }

    doc_status_counts = {
        "Draft": len([d for d in data if d["doc_status"] == "Draft"]),
        "Submitted": len([d for d in data if d["doc_status"] == "Submitted"]),
        "Not Available": len([d for d in data if d["doc_status"] == "Not Available"])
    }

    total_employees = len(data)
    marked_attendance = total_employees - status_counts["Not Marked"]
    attendance_percentage = (status_counts["Present"] / marked_attendance * 100) if marked_attendance else 0

    message = f"""<div style='font-family: system-ui; padding: 15px;'>
        <h3>Attendance Summary for {filters.get('date', 'Today')}</h3>
        <p>Total Employees: {total_employees}</p>
        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;'>
            <div style='background: #f0f4f8; padding: 10px; border-radius: 5px;'>
                <h4>Status Distribution</h4>
                <ul style='list-style-type: none; padding-left: 0;'>
                    <li>Present: {status_counts['Present']}</li>
                    <li>Absent: {status_counts['Absent']}</li>
                    <li>On Leave: {status_counts['On Leave']}</li>
                    <li>Not Marked: {status_counts['Not Marked']}</li>
                </ul>
            </div>
            <div style='background: #f0f4f8; padding: 10px; border-radius: 5px;'>
                <h4>Document Status</h4>
                <ul style='list-style-type: none; padding-left: 0;'>
                    <li>Draft: {doc_status_counts['Draft']}</li>
                    <li>Submitted: {doc_status_counts['Submitted']}</li>
                    <li>Not Available: {doc_status_counts['Not Available']}</li>
                </ul>
            </div>
        </div>
    </div>"""

    return columns, data, message, None, None

def get_columns():
    return [
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 150
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Designation"),
            "fieldname": "designation",
            "fieldtype": "Link",
            "options": "Designation",
            "width": 150
        },
        {
            "label": _("Route"),
            "fieldname": "route",
            "fieldtype": "Link",
            "options": "Route",
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
            "label": _("Zone"),
            "fieldname": "zone",
            "fieldtype": "Link",
            "options": "Zone",
            "width": 150
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Document Status"),
            "fieldname": "doc_status",
            "fieldtype": "Data",
            "width": 120
        }
    ]

def get_point_wise_attendance(filters):
    # Set default date to today if not provided
    if not filters.get("date"):
        filters["date"] = frappe.utils.today()

    # First get allowed points based on permissions and filters
    point_filters = {"is_active": 1}
    
    if filters.get("zones"):
        point_filters["zone_name"] = ("in", filters.get("zones"))
    
    allowed_points = frappe.get_list("Point", 
        fields=["name", "zone_name"],
        filters=point_filters
    )
    
    point_zone_map = {p.name: p.zone_name for p in allowed_points}
    
    # Get all employees
    employee_filters = {
        "company": ("in", filters.companies),
        "status": "Active",
        "custom_point": ("in", [p.name for p in allowed_points])
    }
    
    if filters.get("points"):
        employee_filters["custom_point"] = ("in", [
            p for p in filters.get("points") 
            if p in [ap.name for ap in allowed_points]
        ])

    employees = frappe.get_all(
        "Employee",
        fields=[
            "name", 
            "employee_name", 
            "custom_point",
            "designation",
            "custom_route"
        ],
        filters=employee_filters
    )

    data = []

    for employee in employees:
        # Get attendance for this employee
        attendance = frappe.get_all(
            "Attendance",
            fields=["status", "docstatus"],
            filters={
                "attendance_date": filters.date,
                "employee": employee.name
            },
            order_by="docstatus DESC",  # Prioritize submitted records
            limit=1
        )

        status = "Not Marked"
        doc_status = "Not Available"

        if attendance:
            status = attendance[0].status
            if attendance[0].docstatus == 0:
                doc_status = "Draft"
            elif attendance[0].docstatus == 1:
                doc_status = "Submitted"
            elif attendance[0].docstatus == 2:
                doc_status = "Cancelled"

        row_data = {
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "designation": employee.designation,
            "route": employee.custom_route,
            "zone": point_zone_map.get(employee.custom_point, ""),
            "point": employee.custom_point,
            "status": status,
            "doc_status": doc_status
        }

        data.append(row_data)

    # Sort by zone and point
    data.sort(key=lambda x: (x["zone"] or "", x["point"] or "", x["employee_name"] or ""))

    return data