import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_leave_policy_assignments(filters)

    return columns, data

def get_columns():
    return [
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 180
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": _("Has Assignment"),
            "fieldname": "has_assignment",
            "fieldtype": "Check",
            "width": 100
        },
        # {
        #     "label": _("Leave Policy"),
        #     "fieldname": "leave_policy",
        #     "fieldtype": "Link",
        #     "options": "Leave Policy",
        #     "width": 180
        # },
        {
            "label": _("Effective From"),
            "fieldname": "effective_from",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Effective To"),
            "fieldname": "effective_to",
            "fieldtype": "Date",
            "width": 120
        },
        # {
        #     "label": _("Assignment Based On"),
        #     "fieldname": "assignment_based_on",
        #     "fieldtype": "Data",
        #     "width": 150
        # },
        # {
        #     "label": _("Leave Period"),
        #     "fieldname": "leave_period",
        #     "fieldtype": "Link",
        #     "options": "Leave Period",
        #     "width": 150
        # },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]
    
def get_leave_policy_assignments(filters):
    # Get the logged in user
    user = frappe.session.user
    
    # Get employees that the user is responsible for
    employee_filters = {
        "status": "Active"
    }
    
    # Add company filter if specified
    if filters.get("company"):
        employee_filters["company"] = filters.get("company")
    
    # Get permission conditions for Employee doctype
  
    # Get all employees user has access to
    employees = frappe.get_all(
        "Employee",
        fields=["name", "employee_name", "designation", "department"],
        filters=employee_filters
    )
    
    if not employees:
        return []
    
    # Get leave policy assignments for these employees
    assignments = frappe.get_all(
        "Leave Policy Assignment",
        fields=[
            "employee",
            "employee_name",
            # "leave_policy",
            "effective_from",
            "effective_to",
            "assignment_based_on",
            # "leave_period",
            "docstatus",
            "name"
        ],
        filters={
            "employee": ["in", [emp.name for emp in employees]],
            "docstatus": 1
        },
        order_by="effective_from desc"
    )
    
    # Create a mapping of employee to their latest assignment
    employee_assignments = {}
    for assignment in assignments:
        if assignment.employee not in employee_assignments:
            employee_assignments[assignment.employee] = assignment
    
    # Prepare final data
    data = []
    for employee in employees:
        assignment = employee_assignments.get(employee.name)
        
        if filters.get("show_only_without_assignment") and assignment:
            continue
            
        row = {
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "has_assignment": 1 if assignment else 0,
            "leave_policy": assignment.leave_policy if assignment else None,
            "effective_from": assignment.effective_from if assignment else None,
            "effective_to": assignment.effective_to if assignment else None,
            "assignment_based_on": assignment.assignment_based_on if assignment else None,
            "leave_period": assignment.leave_period if assignment else None,
            "status": "Submitted" if assignment and assignment.docstatus == 1 else "No Assignment"
        }
        data.append(row)
    
    # Sort by employee name
    data.sort(key=lambda x: x["employee_name"])
    
    return data