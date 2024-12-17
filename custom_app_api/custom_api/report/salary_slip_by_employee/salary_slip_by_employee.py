import frappe
from frappe import _
from frappe.utils import getdate

def execute(filters=None):
    filters = frappe._dict(filters or {})
    
    columns = get_columns(filters)
    data = get_salary_slip_data(filters)

    return columns, data

def get_columns(filters):
    """Dynamic columns based on basic info and earning types"""
    columns = [
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
    ]

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

    return columns

def get_earning_types(filters):
    """Get all unique earning types from salary slips"""
    query = """
        SELECT DISTINCT salary_component 
        FROM `tabSalary Detail` sd
        JOIN `tabSalary Slip` ss ON sd.parent = ss.name
        WHERE ss.docstatus = 1
        AND MONTH(ss.posting_date) = %(month)s
        AND YEAR(ss.posting_date) = %(year)s
        AND sd.parentfield = 'earnings'
        ORDER BY salary_component
    """
    
    earning_types = frappe.db.sql(query, {
        'month': int(filters.month),
        'year': int(filters.year)
    }, as_dict=1)

    return [d.salary_component for d in earning_types]

def get_salary_slip_data(filters):
    """Get salary slip data with employee details and earnings"""
    query = """
        SELECT 
            ss.name,
            ss.employee,
            ss.employee_name,
            e.custom_route,
            e.custom_point,
            e.custom_area,
            e.custom_zone,
            e.branch
        FROM `tabSalary Slip` ss
        JOIN `tabEmployee` e ON ss.employee = e.name
        WHERE ss.docstatus = 1
        AND MONTH(ss.posting_date) = %(month)s
        AND YEAR(ss.posting_date) = %(year)s
    """

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

    # Get earnings data
    earnings_query = """
        SELECT 
            parent,
            salary_component,
            amount
        FROM `tabSalary Detail`
        WHERE parentfield = 'earnings'
        AND parent IN %(salary_slips)s
    """

    earnings = frappe.db.sql(earnings_query, {
        'salary_slips': tuple([d.name for d in salary_slips]) or ("",)
    }, as_dict=1)

    # Organize earnings by salary slip
    earnings_data = {}
    for earning in earnings:
        if earning.parent not in earnings_data:
            earnings_data[earning.parent] = {}
        earnings_data[earning.parent][earning.salary_component] = earning.amount

    # Prepare final data
    data = []
    earning_types = get_earning_types(filters)
    
    for slip in salary_slips:
        row = {
            "employee": slip.employee,
            "employee_name": slip.employee_name,
            "route": slip.custom_route,
            "point": slip.custom_point,
            "area": slip.custom_area,
            "zone": slip.custom_zone,
            "branch": slip.branch
        }

        # Add earnings
        total_earnings = 0
        slip_earnings = earnings_data.get(slip.name, {})
        
        for earning_type in earning_types:
            amount = slip_earnings.get(earning_type, 0)
            row[frappe.scrub(earning_type)] = amount
            total_earnings += amount

        row["total_earnings"] = total_earnings
        data.append(row)

    return data
