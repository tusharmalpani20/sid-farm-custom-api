import frappe
from frappe.utils import today, date_diff, add_days, getdate, now_datetime
from custom_app_api.doc_events.employee import create_job_opening_for_route

def check_notice_period_completion():
    """
    Cron job to check and update employees who have completed their notice period.
    - Finds employees in notice period with Active status
    - Checks if notice period is complete
    - Updates status to Left and sets relieving date
    - Creates job openings for L5 grade employees
    Runs daily.
    """
    try:
        frappe.logger().info("Starting notice period completion check")
        
        # Get employees in notice period
        employees = frappe.get_all(
            "Employee",
            filters={
                "custom_is_notice_period": 1,
                "status": "Active"
            },
            fields=[
                "name", "employee_name", "custom_notice_period_marked_at",
                "notice_number_of_days", "grade", "custom_route"
            ]
        )
        
        frappe.logger().info(f"Found {len(employees)} employees in notice period to check")

        for employee in employees:
            try:
                # Calculate days elapsed since notice period started
                notice_start_date = getdate(employee.custom_notice_period_marked_at)
                days_elapsed = date_diff(today(), notice_start_date)
                
                # Check if notice period is complete
                if days_elapsed >= employee.notice_number_of_days:
                    frappe.logger().info(
                        f"Employee {employee.name} has completed notice period. "
                        f"Days elapsed: {days_elapsed}, Required: {employee.notice_number_of_days}"
                    )
                    
                    # Calculate actual relieving date
                    relieving_date = add_days(notice_start_date, employee.notice_number_of_days)
                    
                    # Update employee status
                    emp_doc = frappe.get_doc("Employee", employee.name)
                    emp_doc.db_set({
                        'status': 'Left',
                        'relieving_date': relieving_date
                    }, update_modified=False)
                    
                    # Create job opening for L5 grade employees
                    if employee.grade == "L5" and employee.custom_route:
                        create_job_opening_for_route(emp_doc)
                    
                    frappe.logger().info(
                        f"Updated employee {employee.name} ({employee.employee_name}) to Left status. "
                        f"Relieving date: {relieving_date}"
                    )

            except Exception as emp_error:
                frappe.log_error(
                    message=f"Error processing employee {employee.name}: {frappe.get_traceback()}",
                    title=f"Notice Period Completion Error - {employee.name}"
                )
        
        frappe.db.commit()
        
        # Log completion
        frappe.logger().info("Completed notice period completion check")

    except Exception as e:
        frappe.log_error(
            message=f"Error in notice period completion check: {frappe.get_traceback()}",
            title="Notice Period Completion Check Error"
        )
