import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils.nestedset import get_descendants_of

def execute(filters=None):
    if not filters:
        filters = {}

    if filters.get("company"):
        filters.companies = [filters.get("company")]
        if filters.get("include_company_descendants"):
            filters.companies.extend(get_descendants_of("Company", filters.get("company")))

    # Get columns and data
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
    earning_types = frappe.db.sql("""
        SELECT DISTINCT salary_component 
        FROM `tabSalary Detail` sd
        JOIN `tabSalary Slip` ss ON sd.parent = ss.name
        WHERE ss.docstatus = 1
        AND ss.company IN %(companies)s
        AND MONTH(ss.start_date) = %(month)s
        AND YEAR(ss.start_date) = %(year)s
        AND sd.parentfield = 'earnings'
        ORDER BY salary_component
    """, {
        'companies': filters.companies,
        'month': filters.month,
        'year': filters.year
    }, as_dict=1)

    return [d.salary_component for d in earning_types]

def get_salary_slip_data(filters):
    """Get salary slip data with employee details and earnings"""
    # Get allowed employees based on permissions
    allowed_employees = get_allowed_employees()

    # Get all salary slips for the period
    salary_slips = frappe.db.sql("""
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
        AND ss.company IN %(companies)s
        AND MONTH(ss.start_date) = %(month)s
        AND YEAR(ss.start_date) = %(year)s
        AND ss.employee IN %(employees)s
    """, {
        'companies': filters.companies,
        'month': filters.month,
        'year': filters.year,
        'employees': allowed_employees
    }, as_dict=1)

    # Get all earnings for these salary slips
    earnings_data = {}
    if salary_slips:
        earnings = frappe.db.sql("""
            SELECT 
                parent,
                salary_component,
                amount
            FROM `tabSalary Detail`
            WHERE parentfield = 'earnings'
            AND parent IN %(salary_slips)s
        """, {
            'salary_slips': [d.name for d in salary_slips]
        }, as_dict=1)

        # Organize earnings by salary slip
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

def get_allowed_employees():
    """Get list of employees that the current user has permission to see"""
    return frappe.get_list("Employee", 
        fields=["name"],
        filters={"status": "Active"}
    )
