import frappe
from frappe.utils import today, getdate

def calculate_extra_km_salary():
    """
    Cron job to calculate additional salary for delivery employees who exceed their travel limit.
    Runs daily at 11 PM.
    """
    try:
        # Get today's attendance records
        attendance_records = frappe.get_all(
            "Attendance",
            filters={
                "attendance_date": today(),
                "status": "Present",
                "custom_kilometers_travelled": [">", 0]  # Only get records with km traveled
            },
            fields=["employee", "custom_kilometers_travelled", "name"]
        )

        for attendance in attendance_records:
            # Get employee details including designation
            employee = frappe.get_doc("Employee", attendance.employee)
            
            # Check if employee is a delivery person and has a travel limit set
            if not employee.designation or "Delivery" not in employee.designation:
                continue
            
            # Skip if travel limit is not set (0 or None)
            if not employee.custom_travel_limit:
                continue

            # Calculate extra kilometers
            extra_km = attendance.custom_kilometers_travelled - employee.custom_travel_limit

            # If extra kilometers exist, create Additional Salary
            if extra_km > 0:
                amount = extra_km * 3  # Rs. 3 per extra kilometer

                # Create descriptive reason
                reason = (
                    # f"Extra KM Allowance for {frappe.utils.formatdate(today())}\n"
                    f"Total KMs Travelled: {attendance.custom_kilometers_travelled} km\n"
                    f"Company Provision: {employee.custom_travel_limit} km\n"
                    f"Extra KMs: {extra_km} km\n"
                    f"Rate per Extra KM: Rs. 3\n"
                    # f"Total Amount: Rs. {amount}"
                )

                # Create Additional Salary entry
                additional_salary = frappe.get_doc({
                    "doctype": "Additional Salary",
                    "employee": attendance.employee,
                    "salary_component": "Advance Salary",
                    "amount": amount,
                    "payroll_date": today(),
                    "company": employee.company,
                    "ref_doctype": "Attendance",
                    "ref_docname": attendance.name,
                    "custom_reason": reason,
                    "overwrite_salary_structure_amount": 1
                })

                # Only save the document, don't submit
                additional_salary.insert(ignore_permissions=True)
                additional_salary.submit()
                frappe.db.commit()

                frappe.logger().info(
                    f"Additional Salary created for {employee.employee_name} "
                    f"for extra {extra_km} km. Amount: Rs. {amount}"
                )

    except Exception as e:
        frappe.logger().error(f"Error in calculate_extra_km_salary: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Calculate Extra KM Salary Error")
