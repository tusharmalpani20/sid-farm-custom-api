import frappe
from frappe import _
from frappe.utils import getdate

def execute(filters=None):
    filters = frappe._dict(filters or {})
    
    columns = get_columns(filters)
    data = get_salary_slip_data(filters)

    return columns, data

def get_columns(filters):
    """Dynamic columns based on basic info, earnings, and deductions"""
    columns = [
        {
            "label": _("Salary Slip ID"),
            "fieldname": "salary_slip_id",
            "fieldtype": "Link",
            "options": "Salary Slip",
            "width": 140
        }
    ]

    # Add status column if include_draft is checked
    if filters.get("include_draft"):
        columns.append({
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        })

    # Add other basic columns
    columns.extend([
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Route"),
            "fieldname": "route",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Point"),
            "fieldname": "point",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Area"),
            "fieldname": "area",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Zone"),
            "fieldname": "zone",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Branch"),
            "fieldname": "branch",
            "fieldtype": "Data",
            "width": 120
        }
    ])

    # Add columns for each earning type
    earning_types = get_earning_types(filters)
    for earning_type in earning_types:
        columns.append({
            "label": _(earning_type),
            "fieldname": frappe.scrub(earning_type),
            "fieldtype": "Currency",
            "width": 120
        })

    # Add total earnings column
    columns.append({
        "label": _("Total Earnings"),
        "fieldname": "total_earnings",
        "fieldtype": "Currency",
        "width": 120
    })

    # Add columns for each deduction type
    deduction_types = get_deduction_types(filters)
    for deduction_type in deduction_types:
        columns.append({
            "label": _(deduction_type),
            "fieldname": frappe.scrub(deduction_type),
            "fieldtype": "Currency",
            "width": 120
        })

    # Add total deductions and net pay columns
    columns.extend([
        {
            "label": _("Total Deductions"),
            "fieldname": "total_deductions",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Net Pay"),
            "fieldname": "net_pay",
            "fieldtype": "Currency",
            "width": 120
        }
    ])

    return columns

def get_earning_types(filters):
    """Get all unique earning types from salary slips"""
    docstatus_condition = "ss.docstatus IN (0, 1)" if filters.get("include_draft") else "ss.docstatus = 1"
    
    query = """
        SELECT DISTINCT salary_component 
        FROM `tabSalary Detail` sd
        JOIN `tabSalary Slip` ss ON sd.parent = ss.name
        WHERE {docstatus_condition}
        AND MONTH(ss.posting_date) = %(month)s
        AND YEAR(ss.posting_date) = %(year)s
        AND sd.parentfield = 'earnings'
        ORDER BY salary_component
    """.format(docstatus_condition=docstatus_condition)
    
    earning_types = frappe.db.sql(query, {
        'month': int(filters.month),
        'year': int(filters.year)
    }, as_dict=1)

    return [d.salary_component for d in earning_types]

def get_deduction_types(filters):
    """Get all unique deduction types from salary slips"""
    docstatus_condition = "ss.docstatus IN (0, 1)" if filters.get("include_draft") else "ss.docstatus = 1"
    
    query = """
        SELECT DISTINCT salary_component 
        FROM `tabSalary Detail` sd
        JOIN `tabSalary Slip` ss ON sd.parent = ss.name
        WHERE {docstatus_condition}
        AND MONTH(ss.posting_date) = %(month)s
        AND YEAR(ss.posting_date) = %(year)s
        AND sd.parentfield = 'deductions'
        ORDER BY salary_component
    """.format(docstatus_condition=docstatus_condition)
    
    deduction_types = frappe.db.sql(query, {
        'month': int(filters.month),
        'year': int(filters.year)
    }, as_dict=1)

    return [d.salary_component for d in deduction_types]

def get_salary_slip_data(filters):
    """Get salary slip data with employee details, earnings, and deductions"""
    docstatus_condition = "ss.docstatus IN (0, 1)" if filters.get("include_draft") else "ss.docstatus = 1"
    
    query = """
        SELECT 
            ss.name as salary_slip_id,
            ss.docstatus,
            ss.employee,
            ss.employee_name,
            ss.net_pay,
            e.custom_route,
            e.custom_point,
            e.custom_area,
            e.custom_zone,
            e.branch
        FROM `tabSalary Slip` ss
        JOIN `tabEmployee` e ON ss.employee = e.name
        WHERE {docstatus_condition}
        AND MONTH(ss.posting_date) = %(month)s
        AND YEAR(ss.posting_date) = %(year)s
    """.format(docstatus_condition=docstatus_condition)

    # Add point filter if specified
    if filters.get("points"):
        query += " AND e.custom_point IN %(points)s"

    params = {
        'month': int(filters.month),
        'year': int(filters.year),
        'points': tuple(filters.get("points")) if filters.get("points") else None
    }

    salary_slips = frappe.db.sql(query, params, as_dict=1)

    # If no salary slips found, return empty list
    if not salary_slips:
        return []

    # Get both earnings and deductions data
    components_query = """
        SELECT 
            parent,
            parentfield,
            salary_component,
            amount
        FROM `tabSalary Detail`
        WHERE parent IN %(salary_slips)s
        AND parentfield IN ('earnings', 'deductions')
    """

    components = frappe.db.sql(components_query, {
        'salary_slips': tuple([d.salary_slip_id for d in salary_slips]) or ("",)
    }, as_dict=1)

    # Organize components by salary slip
    earnings_data = {}
    deductions_data = {}
    
    for comp in components:
        if comp.parentfield == 'earnings':
            if comp.parent not in earnings_data:
                earnings_data[comp.parent] = {}
            earnings_data[comp.parent][comp.salary_component] = comp.amount
        else:  # deductions
            if comp.parent not in deductions_data:
                deductions_data[comp.parent] = {}
            deductions_data[comp.parent][comp.salary_component] = comp.amount

    # Prepare final data
    data = []
    earning_types = get_earning_types(filters)
    deduction_types = get_deduction_types(filters)
    
    for slip in salary_slips:
        row = {
            "salary_slip_id": slip.salary_slip_id,
            "employee": slip.employee,
            "employee_name": slip.employee_name,
            "route": slip.custom_route,
            "point": slip.custom_point,
            "area": slip.custom_area,
            "zone": slip.custom_zone,
            "branch": slip.branch
        }

        # Add status if include_draft is checked
        if filters.get("include_draft"):
            row["status"] = "Draft" if slip.docstatus == 0 else "Submitted"

        # Add earnings
        total_earnings = 0
        slip_earnings = earnings_data.get(slip.salary_slip_id, {})
        
        for earning_type in earning_types:
            amount = slip_earnings.get(earning_type, 0)
            row[frappe.scrub(earning_type)] = amount
            total_earnings += amount

        row["total_earnings"] = total_earnings

        # Add deductions
        total_deductions = 0
        slip_deductions = deductions_data.get(slip.salary_slip_id, {})
        
        for deduction_type in deduction_types:
            amount = slip_deductions.get(deduction_type, 0)
            row[frappe.scrub(deduction_type)] = amount
            total_deductions += amount

        row["total_deductions"] = total_deductions
        row["net_pay"] = slip.net_pay

        data.append(row)

    return data