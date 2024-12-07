import frappe
from frappe import _
from typing import Dict, Any, Optional

def auto_mark_employee_absent() -> None:
    """
    Scheduled job to mark absent for employees with no attendance record
    Designed to run at the end of each day via scheduler
    """
    try:

        #run this only if time is between 05:30 AM to 06:30 AM
        # current_time = datetime.now().time()
        # if current_time < time(5, 30) or current_time > time(6, 30):
        #     print("Not the right time to mark absent")
        #     return

        today = frappe.utils.nowdate()
        
        
        # Get all active employees
        active_employees = frappe.get_all(
            "Employee",
            filters={
                "status": "Active",
                "date_of_joining": ["<=", today]
            },
            fields=["name", "employee_name", "company", "department"]
        )

        if not active_employees:
            frappe.logger().info("No active employees found for marking absent")
            return

        # Get today's attendance records
        existing_attendance = frappe.get_all(
            "Attendance",
            filters={
                "attendance_date": today,
                "docstatus": ["!=", 2]  # Not cancelled
            },
            fields=["employee"]
        )

        # Create set of employees who already have attendance
        employees_with_attendance = {att.employee for att in existing_attendance}
        
        absent_count = 0
        error_count = 0

        # Create absent records for employees without attendance
        for employee in active_employees:
            if employee.name not in employees_with_attendance:
                try:
                    # Create new attendance record
                    attendance = frappe.get_doc({
                        "doctype": "Attendance",
                        "employee": employee.name,
                        "employee_name": employee.employee_name,
                        "attendance_date": today,
                        "status": "Absent",
                        "company": employee.company,
                        "department": employee.department
                    })
                    
                    attendance.insert()
                    attendance.submit()
                    absent_count += 1
                    
                except Exception as e:
                    error_count += 1
                    frappe.log_error(
                        message=f"Error marking absent for employee {employee.name}: {str(e)}",
                        title="Auto Mark Absent Error"
                    )

        # Log summary
        frappe.logger().info(
            f"Auto Mark Absent Summary - Date: {today}\n"
            f"Total Active Employees: {len(active_employees)}\n"
            f"Existing Attendance: {len(existing_attendance)}\n"
            f"Marked Absent: {absent_count}\n"
            f"Errors: {error_count}"
        )

    except Exception as e:
        frappe.log_error(
            message=f"Error in auto mark absent job: {str(e)}",
            title="Auto Mark Absent Job Failed"
        )