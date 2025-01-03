import frappe
from datetime import datetime
from frappe.utils import getdate

def generate_route_payout():
    """
    Daily cron job to calculate and distribute route payout.
    Runs daily for routes with additional payout enabled and L5 grade employees present.
    """
    try:
        current_date = getdate()
        
        frappe.logger().info(f"Starting route payout calculation for date: {current_date}")
        
        # Get all routes with additional payout enabled
        routes = frappe.get_all("Route", 
            filters={
                "has_additional_payout": 1,
                "payout_amount": [">", 0]
            },
            fields=["name", "route_name", "payout_amount"]
        )
        
        processed_routes = 0
        payout_entries_created = 0
        errors = []

        for route in routes:
            try:
                # Find L5 grade employee with attendance for this route
                attendance_records = frappe.get_all(
                    "Attendance",
                    filters={
                        "custom_route": route.name,
                        "attendance_date": current_date,
                        "status": "Present",
                        "docstatus": 1
                    },
                    fields=["employee"]
                )

                if not attendance_records:
                    continue

                # Get L5 employees from attendance records
                for attendance in attendance_records:
                    employee = frappe.get_doc("Employee", attendance.employee)
                    
                    # Skip if not L5 grade
                    if employee.grade != "L5" or employee.status != "Active":
                        continue

                    # Check if payout already exists for this date
                    existing_payout = frappe.get_all(
                        "Additional Salary",
                        filters={
                            "employee": employee.name,
                            "salary_component": "Route Payout",
                            "payroll_date": current_date,
                            "custom_route": route.name,
                            "docstatus": 1
                        }
                    )

                    if existing_payout:
                        frappe.logger().info(
                            f"Payout already exists for {employee.employee_name} "
                            f"on route {route.route_name} for {current_date}"
                        )
                        continue

                    # Format reason
                    reason = f"""Daily Route Payout for {current_date.strftime('%d-%m-%Y')}
Route: {route.route_name}
Payout Amount: ₹{route.payout_amount:,.2f}
Employee: {employee.employee_name} (Grade: L5)"""

                    # Create Additional Salary entry
                    additional_salary = frappe.get_doc({
                        "doctype": "Additional Salary",
                        "employee": employee.name,
                        "employee_name": employee.employee_name,
                        "salary_component": "Route Payout",
                        "amount": route.payout_amount,
                        "payroll_date": current_date,
                        "company": employee.company,
                        "custom_route": route.name,
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
                    
                    # Force update workflow state and docstatus directly in the database
                    frappe.db.set_value('Additional Salary', additional_salary.name, {
                        'workflow_state': 'Submitted',
                        'docstatus': 1
                    })
                    
                    # Reload the document to reflect the changes
                    additional_salary.reload()
                    
                    # Skip the submit() call since we've already set docstatus
                    # additional_salary.submit()
                    payout_entries_created += 1

                    frappe.logger().info(
                        f"Created daily route payout for {employee.employee_name} "
                        f"- ₹{route.payout_amount:,.2f} for route {route.route_name}"
                    )

                processed_routes += 1

            except Exception as e:
                error_msg = f"Error processing route {route.route_name}: {str(e)}"
                errors.append(error_msg)
                frappe.logger().error(error_msg)
                continue

        # Commit all changes
        frappe.db.commit()

        # Log summary
        summary = f"""
Daily Route Payout Calculation completed for {current_date}:
- Total routes processed: {processed_routes}
- Payout entries created: {payout_entries_created}
- Errors encountered: {len(errors)}
- Timestamp: {datetime.now()}
"""
        frappe.logger().info(summary)

        # If there were errors, create an error log
        if errors:
            frappe.log_error(
                title=f"Route Payout Calculation Errors - {current_date}",
                message="\n".join(errors)
            )

    except Exception as e:
        error_msg = f"Route payout calculation failed: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error(title="Route Payout Calculation Failed", message=error_msg)
        raise
