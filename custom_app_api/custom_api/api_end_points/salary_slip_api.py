import frappe
from frappe import _
from frappe.utils import today

@frappe.whitelist(methods=['POST'])
def create_salary_slip():
    try:
        # Get JSON data from request
        data = frappe.request.get_json()
        
        # Validate employee_id is provided
        if not data or 'employee_id' not in data:
            frappe.throw(_("employee_id is required in request body"))
            
        employee_id = data['employee_id']
        
        # Validate employee exists
        if not frappe.db.exists("Employee", employee_id):
            frappe.throw(_("Employee {0} does not exist").format(employee_id))
        
        # Check for existing submitted salary slip this month
        existing_slip = frappe.db.exists(
            "Salary Slip",
            {
                "employee": employee_id,
                "docstatus": 1,  # 1 means submitted
                "start_date": [">=", frappe.utils.get_first_day(today())],
                "end_date": ["<=", frappe.utils.get_last_day(today())]
            }
        )
        
        if existing_slip:
            frappe.throw(_("A salary slip for {0} already exists for this month").format(employee_id))
        
        # Check for existing draft salary slip
        draft_slip = frappe.db.get_value(
            "Salary Slip",
            {
                "employee": employee_id,
                "docstatus": 0,  # 0 means draft
                "start_date": [">=", frappe.utils.get_first_day(today())],
                "end_date": ["<=", frappe.utils.get_last_day(today())]
            },
            "name"
        )
        
        if draft_slip:
            # Get existing draft and update it
            salary_slip = frappe.get_doc("Salary Slip", draft_slip)
            salary_slip.get_emp_and_working_day_details()
            salary_slip.save()
        else:
            # Create new salary slip
            salary_slip = frappe.new_doc("Salary Slip")
            salary_slip.employee = employee_id
            salary_slip.posting_date = today()
            salary_slip.company = frappe.db.get_single_value("Global Defaults", "default_company")
            
            # Set other default values
            salary_slip.salary_slip_based_on_timesheet = 0
            salary_slip.deduct_tax_for_unclaimed_employee_benefits = 0
            salary_slip.deduct_tax_for_unsubmitted_tax_exemption_proof = 0
            
            # Get employee details and calculate salary structure
            salary_slip.get_emp_and_working_day_details()
            salary_slip.save()
        
        return {
            "status": "success",
            "message": "Salary slip created/updated successfully",
            "salary_slip": {
                "name": salary_slip.name,
                "employee": salary_slip.employee,
                "employee_name": salary_slip.employee_name,
                "posting_date": salary_slip.posting_date,
                "start_date": salary_slip.start_date,
                "end_date": salary_slip.end_date,
                "gross_pay": salary_slip.gross_pay,
                "net_pay": salary_slip.net_pay,
                "total_deduction": salary_slip.total_deduction
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Salary Slip Creation Failed"))
        return {
            "status": "error",
            "message": str(e)
        }
