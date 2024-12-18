import frappe
from frappe import _
from datetime import datetime
from ..custom_api.api_end_points.salary_slip_api import create_salary_slip

def generate_salary_slips_for_active_employees():
    # Add time check
    # current_hour = datetime.now().hour
    # if current_hour < 23:  # Before 11:00 PM
    #     print(f"Skipping salary slip generation. Current hour: {current_hour}. Will run after 11:00 PM")
    #     return
    
    try:
        # Get all active employees
        active_employees = frappe.get_all(
            "Employee",
            filters={
                "status": "Active"
            },
            fields=["name", "employee_name"]
        )

        success_count = 0
        error_count = 0
        skipped_count = 0
        
        print(f"Starting salary slip generation for {len(active_employees)} employees")
        
        for employee in active_employees:
            try:
                employee_id = employee.name
                print(f"\nProcessing employee: {employee_id} ({employee.employee_name})")
                
                # First, check if employee has a salary structure assigned
                salary_structure = frappe.db.get_value(
                    "Salary Structure Assignment",
                    {"employee": employee_id, "docstatus": 1},
                    "salary_structure"
                )
                
                if not salary_structure:
                    print(f"❌ No salary structure found for {employee_id}")
                    error_count += 1
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
                        print(f"❌ No holiday list found for {employee_id} or company")
                        error_count += 1
                        continue

                # Check for existing submitted salary slip this month
                existing_slip = frappe.db.exists(
                    "Salary Slip",
                    {
                        "employee": employee_id,
                        "start_date": [">=", frappe.utils.get_first_day(frappe.utils.today())],
                        "end_date": ["<=", frappe.utils.get_last_day(frappe.utils.today())],
                        # "docstatus": 1  # Only check for submitted slips
                        "workflow_state": ["not in", ["Pending"]]
                    }
                )
                
                if existing_slip:
                    print(f"⏩ Skipping {employee_id} - submitted salary slip already exists")
                    skipped_count += 1
                    continue

                # Check for existing draft salary slip
                draft_slip = frappe.db.get_value(
                    "Salary Slip",
                    {
                        "employee": employee_id,
                        # "docstatus": 0,  # Check for draft
                        "workflow_state": ["in", ["Pending"]],
                        "start_date": [">=", frappe.utils.get_first_day(frappe.utils.today())],
                        "end_date": ["<=", frappe.utils.get_last_day(frappe.utils.today())]
                    },
                    "name"
                )

                if draft_slip:
                    # Update existing draft
                    salary_slip = frappe.get_doc("Salary Slip", draft_slip)
                    salary_slip.get_emp_and_working_day_details()
                    salary_slip.save()
                    print(f"✅ Successfully updated draft salary slip for {employee_id}")
                else:
                    # Create new salary slip
                    salary_slip = frappe.new_doc("Salary Slip")
                    salary_slip.employee = employee_id
                    salary_slip.posting_date = frappe.utils.today()
                    salary_slip.start_date = frappe.utils.get_first_day(frappe.utils.today())
                    salary_slip.end_date = frappe.utils.get_last_day(frappe.utils.today())
                    salary_slip.company = frappe.db.get_single_value("Global Defaults", "default_company")
                    
                    # Set other default values
                    salary_slip.salary_slip_based_on_timesheet = 0
                    salary_slip.deduct_tax_for_unclaimed_employee_benefits = 0
                    salary_slip.deduct_tax_for_unsubmitted_tax_exemption_proof = 0
                    
                    # Get employee details and calculate salary structure
                    salary_slip.get_emp_and_working_day_details()
                    salary_slip.save()
                    
                    print(f"✅ Successfully created salary slip for {employee_id}")
                    success_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"❌ Error processing {employee_id}: {str(e)}")
                frappe.log_error(
                    message=f"Salary slip creation failed for employee {employee.name}: {str(e)}",
                    title="Salary Slip Creation Error"
                )

        print("\n=== Summary ===")
        print(f"Total Employees: {len(active_employees)}")
        print(f"Success: {success_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Errors: {error_count}")
        
    except Exception as e:
        print(f"❌ Major error in salary slip generation: {str(e)}")
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Salary Slip Generation Error"
        )