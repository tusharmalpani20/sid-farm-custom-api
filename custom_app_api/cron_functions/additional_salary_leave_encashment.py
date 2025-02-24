import frappe
from frappe.utils import today, date_diff, add_months, getdate, get_first_day, get_last_day
from datetime import datetime

def check_and_award_leave_encashment():
    """
    Daily cron job to check and award leave encashment bonus to employees
    who haven't taken any leave in their previous 3-month cycle.
    Cycles are based on employee's joining date and repeat every 3 months.
    """
    try:
        current_date = getdate()
        frappe.logger().info("Starting leave encashment bonus check")
        
        # Get all active employees
        active_employees = frappe.get_all(
            "Employee",
            filters={
                "status": "Active",
                "date_of_joining": ["<=", add_months(current_date, -3)]  # Joined at least 3 months ago
            },
            fields=["name", "employee_name", "date_of_joining", "company"]
        )
        
        processed_count = 0
        bonus_awarded = 0
        errors = []
        
        for employee in active_employees:
            try:
                joining_date = employee.date_of_joining
                
                # Calculate the most recent completed 3-month cycle
                months_since_joining = date_diff(current_date, joining_date) // 30
                completed_cycles = months_since_joining // 3
                
                if completed_cycles == 0:
                    continue
                
                # Calculate the last cycle dates
                cycle_start = add_months(joining_date, (completed_cycles - 1) * 3)
                cycle_end = add_months(cycle_start, 3)
                
                # Only process if today is the day after cycle end
                if current_date != add_months(cycle_end, 0):
                    continue
                
                # Skip if we've already processed this cycle
                existing_bonus = frappe.db.exists(
                    "Additional Salary",
                    {
                        "employee": employee.name,
                        "salary_component": "Leave Encashment",
                        "payroll_date": cycle_end,
                        "docstatus": 1
                    }
                )
                
                if existing_bonus:
                    continue
                
                # Check for any leaves in this period
                leave_count = frappe.db.count(
                    "Attendance",
                    filters={
                        "employee": employee.name,
                        "attendance_date": ["between", (cycle_start, cycle_end)],
                        "status": "On Leave",
                        "docstatus": 1
                    }
                )
                
                if leave_count == 0:
                    # Format reason
                    reason = f"""Leave Encashment Bonus
3-Month Cycle: {cycle_start.strftime('%d-%m-%Y')} to {cycle_end.strftime('%d-%m-%Y')}
Cycle #{completed_cycles}
No leaves taken during this period."""

                    # Create Additional Salary entry
                    additional_salary = frappe.get_doc({
                        "doctype": "Additional Salary",
                        "employee": employee.name,
                        "employee_name": employee.employee_name,
                        "salary_component": "Leave Encashment",
                        "amount": 1000,
                        "payroll_date": cycle_end,
                        "company": employee.company,
                        "custom_reason": reason,
                        "overwrite_salary_structure_amount": 1
                    })

                    # Bypass workflow and permissions
                    additional_salary.flags.ignore_permissions = True
                    additional_salary.flags.ignore_validate = True
                    additional_salary.flags.ignore_mandatory = True
                    additional_salary.flags.ignore_workflow = True
                    
                    # Insert without triggering workflow
                    additional_salary.insert()
                    
                    # Force update workflow state and docstatus
                    frappe.db.set_value('Additional Salary', additional_salary.name, {
                        'workflow_state': 'Submitted',
                        'docstatus': 1
                    })
                    
                    # Reload the document
                    additional_salary.reload()
                    
                    bonus_awarded += 1
                    frappe.logger().info(
                        f"Awarded leave encashment bonus to {employee.employee_name} "
                        f"for cycle {cycle_start} to {cycle_end} (Cycle #{completed_cycles})"
                    )
                
                processed_count += 1
                
            except Exception as e:
                error_msg = f"Error processing employee {employee.name}: {str(e)}"
                errors.append(error_msg)
                frappe.logger().error(error_msg)
                continue
        
        # Commit all changes
        frappe.db.commit()
        
        # Log summary
        summary = f"""
Leave Encashment Processing completed:
- Total employees processed: {processed_count}
- Bonuses awarded: {bonus_awarded}
- Errors encountered: {len(errors)}
- Timestamp: {datetime.now()}
"""
        frappe.logger().info(summary)
        
        # Create error log if needed
        if errors:
            frappe.log_error(
                title="Leave Encashment Processing Errors",
                message="\n".join(errors)
            )
            
    except Exception as e:
        frappe.log_error(
            message=f"Error in leave encashment processing: {frappe.get_traceback()}",
            title="Leave Encashment Processing Error"
        )
