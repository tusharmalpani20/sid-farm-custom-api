from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip as ERPNextSalarySlip
import frappe
from frappe import _
from datetime import datetime
import csv
import io
from frappe.utils.file_manager import save_file

class CustomSalarySlip(ERPNextSalarySlip):
    pass

@frappe.whitelist(methods=['POST'])
def generate_salary_slips(year=None, month=None, generate_for_active_employees="true"):
    """
    Generate salary slips for active employees for a specific month
    Args:
        year (int): Year for which to generate salary slips
        month (int): Month for which to generate salary slips
    """
    try:
        # Convert year and month to integers
        year = int(year) if year else datetime.now().year
        month = int(month) if month else datetime.now().month
        
        # Validate month
        if not 1 <= month <= 12:
            return {
                "success": False,
                "message": "Invalid month. Month must be between 1 and 12."
            }

        employee_filter = {}

        if  generate_for_active_employees == "true":
            employee_filter = {
                "status": "Active",
            }
        
        # Get all active employees
        active_employees = frappe.get_all(
            "Employee",
            filters=employee_filter,
            fields=["name", "employee_name"]
        )

        success_count = 0
        error_count = 0
        skipped_count = 0
        error_details = []
        skipped_details = []
        success_details = []
        
        # Create target date for the specified month
        target_date = datetime(year, month, 1)
        
        for employee in active_employees:
            try:
                employee_id = employee.name
                
                # First, check if employee has a salary structure assigned
                salary_structure = frappe.db.get_value(
                    "Salary Structure Assignment",
                    {"employee": employee_id, "docstatus": 1},
                    "salary_structure"
                )
                
                if not salary_structure:
                    error_count += 1
                    error_details.append({
                        "employee": employee_id,
                        "employee_name": employee.employee_name,
                        "error": "No salary structure found"
                    })
                    continue

                # Check for holiday list
                holiday_list = frappe.db.get_value(
                    "Employee",
                    employee_id,
                    "holiday_list"
                )
                
                if not holiday_list:
                    company = frappe.db.get_single_value("Global Defaults", "default_company")
                    holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")
                    
                    if not holiday_list:
                        error_count += 1
                        error_details.append({
                            "employee": employee_id,
                            "employee_name": employee.employee_name,
                            "error": "No holiday list found"
                        })
                        continue

                # Check for existing submitted salary slip
                existing_slip = frappe.db.exists(
                    "Salary Slip",
                    {
                        "employee": employee_id,
                        "start_date": [">=", frappe.utils.get_first_day(target_date)],
                        "end_date": ["<=", frappe.utils.get_last_day(target_date)],
                        "workflow_state": ["not in", ["Pending"]]
                    }
                )
                
                if existing_slip:
                    skipped_count += 1
                    skipped_details.append({
                        "employee": employee_id,
                        "employee_name": employee.employee_name,
                        "reason": "Submitted salary slip already exists"
                    })
                    continue

                # Check for existing draft salary slip
                draft_slip = frappe.db.get_value(
                    "Salary Slip",
                    {
                        "employee": employee_id,
                        "workflow_state": ["in", ["Pending"]],
                        "start_date": [">=", frappe.utils.get_first_day(target_date)],
                        "end_date": ["<=", frappe.utils.get_last_day(target_date)]
                    },
                    "name"
                )

                if draft_slip:
                    # Update existing draft
                    salary_slip = frappe.get_doc("Salary Slip", draft_slip)
                    salary_slip.get_emp_and_working_day_details()
                    salary_slip.save()
                    success_count += 1
                    success_details.append({
                        "employee": employee_id,
                        "employee_name": employee.employee_name,
                        "status": "Updated draft"
                    })
                else:
                    # Create new salary slip
                    salary_slip = frappe.new_doc("Salary Slip")
                    salary_slip.employee = employee_id
                    salary_slip.posting_date = target_date.strftime('%Y-%m-%d')
                    salary_slip.start_date = frappe.utils.get_first_day(target_date)
                    salary_slip.end_date = frappe.utils.get_last_day(target_date)
                    salary_slip.company = frappe.db.get_single_value("Global Defaults", "default_company")
                    
                    # Set other default values
                    salary_slip.salary_slip_based_on_timesheet = 0
                    salary_slip.deduct_tax_for_unclaimed_employee_benefits = 0
                    salary_slip.deduct_tax_for_unsubmitted_tax_exemption_proof = 0
                    
                    # Get employee details and calculate salary structure
                    salary_slip.get_emp_and_working_day_details()
                    salary_slip.save()
                    success_count += 1
                    success_details.append({
                        "employee": employee_id,
                        "employee_name": employee.employee_name,
                        "status": "Created"
                    })
                    
            except Exception as e:
                error_count += 1
                error_details.append({
                    "employee": employee_id,
                    "employee_name": employee.employee_name,
                    "error": str(e)
                })
                frappe.log_error(
                    message=f"Salary slip creation failed for employee {employee.name}: {str(e)}",
                    title="Salary Slip Creation Error"
                )

        # After collecting all results:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Employee ID", "Employee Name", "Status", "Reason"])

        # Successes
        for emp in success_details:
            writer.writerow([emp["employee"], emp["employee_name"], emp["status"], ""])

        # Skipped
        for emp in skipped_details:
            writer.writerow([emp["employee"], emp["employee_name"], "Skipped", emp["reason"]])

        # Errors
        for emp in error_details:
            writer.writerow([emp["employee"], emp["employee_name"], "Error", emp["error"]])

        # Save the file in Frappe
        csv_content = output.getvalue()
        file_name = f"salary_slip_generation_{year}_{month}.csv"
        file_doc = save_file(
            file_name,
            csv_content,
            "User",
            frappe.session.user,
            is_private=0
        )
        file_url = file_doc.file_url

        # Return the file URL in your response
        return {
            "success": True,
            "summary": {
                "total_employees": len(active_employees),
                "success": success_count,
                "skipped": skipped_count,
                "errors": error_count
            },
            "error_details": error_details,
            "skipped_details": skipped_details,
            "success_details": success_details,
            "csv_url": file_url
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Salary Slip Generation Error"
        )
        return {
            "success": False,
            "message": str(e)
        } 