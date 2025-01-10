import frappe
from frappe import _
from frappe.utils import today
from typing import Dict, Any, List
from .attendance_api import verify_dp_token, handle_error_response
from frappe.utils import today, get_first_day, get_last_day
import base64

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


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_salary_slip_history() -> Dict[str, Any]:
    """
    Get all submitted salary slips for the authenticated employee
    Returns last 6 months of salary slips
    """
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 401)
            return result
        
        employee = result["employee"]
        
        # from frappe.utils import add_months
        # six_months_ago = add_months(today(), -6)

        # Get submitted salary slips
        salary_slips = frappe.get_all(
            "Salary Slip",
            fields=[
                "name",
                "posting_date",
                "start_date",
                "end_date",
                "total_working_days",
                "payment_days",
                "gross_pay",
                "total_deduction",
                "net_pay",
                "status"
            ],
            filters=[
                ["employee", "=", employee],
                ["docstatus", "=", 1],  # 1 means submitted
                # ["start_date", ">=", "01-06-2024"]
            ],
            order_by="start_date desc"
        )

        return {
            "success": True,
            "status": "success",
            "message": "Salary slip history retrieved successfully",
            "code": "SALARY_SLIPS_RETRIEVED",
            "data": {
                "salary_slips": salary_slips
            },
            "http_status_code": 200
        }
        
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error fetching salary slip history")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_salary_slip_pdf() -> Dict[str, Any]:
    """
    Get PDF for a specific salary slip
    Required query parameters:
    - slip_id: The name/ID of the salary slip
    """
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 401)
            return result
        
        employee = result["employee"]
        
        # Get salary slip ID from query parameters
        slip_id = frappe.request.args.get('slip_id')
        if not slip_id:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Salary slip ID is required",
                "code": "SLIP_ID_REQUIRED",
                "http_status_code": 400
            }
        
        # Verify salary slip exists and belongs to the employee
        if not frappe.db.exists("Salary Slip", {
            "name": slip_id,
            "employee": employee,
            "docstatus": 1  # Must be submitted
        }):
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "Salary slip not found or unauthorized",
                "code": "SALARY_SLIP_NOT_FOUND",
                "http_status_code": 404
            }
        
        try:
            # Generate PDF
            html = frappe.get_print(
                doctype="Salary Slip",
                name=slip_id,
                print_format="DP-Salary Slip",
                doc=None,
                no_letterhead=0
            )
            
            # Convert HTML to PDF
            pdf = frappe.utils.pdf.get_pdf(html)
            
            # Convert to base64 for mobile transfer
            pdf_base64 = base64.b64encode(pdf).decode('utf-8')
            
            # Get salary slip details
            slip_doc = frappe.get_doc("Salary Slip", slip_id)
            
            return {
                "success": True,
                "status": "success",
                "message": "Salary slip PDF generated successfully",
                "code": "SALARY_SLIP_PDF_GENERATED",
                "data": {
                    "salary_slip": {
                        "name": slip_doc.name,
                        "employee": slip_doc.employee,
                        "employee_name": slip_doc.employee_name,
                        "posting_date": slip_doc.posting_date,
                        "start_date": slip_doc.start_date,
                        "end_date": slip_doc.end_date,
                        "gross_pay": slip_doc.gross_pay,
                        "net_pay": slip_doc.net_pay,
                        "total_deduction": slip_doc.total_deduction,
                        "pdf_data": {
                            "filename": f"salary_slip_{slip_id}.pdf",
                            "base64": pdf_base64,
                            "mime_type": "application/pdf"
                        }
                    }
                },
                "http_status_code": 200
            }
            
        except Exception as pdf_error:
            frappe.log_error(
                title="Salary Slip PDF Generation Error",
                message=f"Error generating PDF for salary slip {slip_id}: {str(pdf_error)}"
            )
            frappe.local.response['http_status_code'] = 500
            return {
                "success": False,
                "status": "error",
                "message": "Error generating salary slip PDF",
                "code": "PDF_GENERATION_ERROR",
                "error_details": str(pdf_error),
                "http_status_code": 500
            }
            
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error fetching salary slip PDF")

@frappe.whitelist(methods=["GET"])
def get_salary_slip_tax_info():
    """
    Get salary slip tax information with filters
    Query Parameters:
    - month: Month name (jan, feb, etc.) - optional, defaults to current month
    - year: YYYY format - optional, defaults to current year
    - grade: Employee grade - optional
    - designation: Employee designation - optional
    """
    try:
        # Get query parameters
        filters = frappe.request.args
        
        # Set default month and year if not provided
        current_date = frappe.utils.today()
        current_month = frappe.utils.getdate(current_date).strftime("%b").lower()
        current_year = frappe.utils.getdate(current_date).year
        
        month = (filters.get('month') or current_month).lower()
        year = filters.get('year') or current_year
        
        # Validate month
        valid_months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        if month not in valid_months:
            frappe.throw(_("Invalid month. Please provide a valid month (jan, feb, etc.)"))
        
        # Convert month name to month number
        month_num = valid_months.index(month) + 1
        
        # Get start and end dates for the month
        start_date = f"{year}-{month_num:02d}-01"
        end_date = frappe.utils.get_last_day(start_date)
        
        # Build salary slip filters
        slip_filters = {
            "start_date": start_date,
            "end_date": end_date,
            # "docstatus": 1  # Only submitted salary slips
        }
        
        # Get salary slips
        salary_slips = frappe.get_all(
            "Salary Slip",
            filters=slip_filters,
            fields=["name", "employee", "employee_name", "gross_pay"]
        )
        
        if not salary_slips:
            return {
                "success": True,
                "message": "No salary slips found for the given criteria",
                "data": {
                    "month": month,
                    "year": year,
                    "records": []
                }
            }
        
        # Get employee filters
        employee_filters = {
            "name": ["in", [slip.employee for slip in salary_slips]]
        }
        
        if filters.get('grade'):
            employee_filters["grade"] = filters.get('grade')
        if filters.get('designation'):
            employee_filters["designation"] = filters.get('designation')
        
        # Get employee details
        employees = frappe.get_all(
            "Employee",
            filters=employee_filters,
            fields=["name", "custom_pan"],
            as_list=False
        )
        
        # Create employee lookup dict
        employee_dict = {emp.name: emp.custom_pan for emp in employees}
        
        # Get TDS component details for each salary slip
        records = []
        for slip in salary_slips:
            # Only include employees that match the grade/designation filters
            if slip.employee not in employee_dict:
                continue
                
            # Get TDS amount
            tds_amount = frappe.db.get_value(
                "Salary Detail",
                {
                    "parent": slip.name,
                    "parentfield": "deductions",
                    "salary_component": "TDS"
                },
                "amount"
            ) or 0
            
            records.append({
                "employee_id": slip.employee,
                "employee_name": slip.employee_name,
                "pan_number": employee_dict.get(slip.employee),
                "taxable_amount": slip.gross_pay,
                "tds": tds_amount
            })
        
        return {
            "success": True,
            "message": "Salary slip tax information retrieved successfully",
            "data": {
                "month": month,
                "year": year,
                "records": records,
                "total_count": len(records)
            },
            "query": {
                "month": month,
                "year": year,
                "grade": filters.get('grade'),
                "designation": filters.get('designation'),
                # "sql_query": query,  # The actual SQL query
                # "parameters": params  # The parameters used in the query
            },
            "http_status_code": 200
        }
        
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error fetching salary slip tax information")

