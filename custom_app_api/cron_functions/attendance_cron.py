import frappe
from frappe import _
from typing import Dict, Any, Optional
from custom_app_api.custom_api.helper_function.calculate_distance import calculate_total_distance

def auto_mark_employee_absent_and_submit_all_todays_attendance() -> None:
    """
    Scheduled job to mark absent for employees with no attendance record
    Designed to run at the end of each day via scheduler
    """
    try:
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

        # Get today's attendance records with full documents
        existing_attendance = frappe.db.get_all(
            "Attendance",
            filters={
                "attendance_date": today,
                "docstatus": ["!=", 2]  # Not cancelled
            },
            fields=["*"]
        )

        # Create set of employees who already have attendance
        employees_with_attendance = {att.employee for att in existing_attendance}
        
        absent_count = 0
        error_count = 0
        submitted_count = 0

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

        # Submit all draft attendance records
        for attendance_record in existing_attendance:
            if attendance_record.docstatus == 0:  # Draft state
                try:
                    attendance_doc = frappe.get_doc("Attendance", attendance_record.name)
                    
                    # Get route tracking records for this attendance
                    route_records = frappe.get_all(
                        "Route Tracking",
                        filters={
                            "attendance": attendance_record.name
                        },
                        fields=["latitude", "longitude", "recorded_at"],
                        order_by="recorded_at ASC"
                    )
                    
                    # Calculate total distance if route records exist
                    if route_records:
                        coordinates = [[record.latitude, record.longitude] 
                                    for record in route_records]
                        total_distance = calculate_total_distance(coordinates)
                        
                        # Update the attendance record with total distance
                        attendance_doc.kilometers_travelled = total_distance
                    
                    # Only set punch out time if it hasn't been set yet
                    if not attendance_doc.custom_mobile_punch_out_at:
                        attendance_doc.custom_mobile_punch_out_at = frappe.utils.now()
                        attendance_doc.custom_is_mobile_auto_punch_out = 1
                    
                    attendance_doc.submit()
                    submitted_count += 1
                    
                except Exception as e:
                    error_count += 1
                    frappe.log_error(
                        message=f"Error submitting attendance {attendance_record.name}: {str(e)}",
                        title="Auto Submit Attendance Error"
                    )

        # Log summary
        frappe.logger().info(
            f"Auto Mark Absent Summary - Date: {today}\n"
            f"Total Active Employees: {len(active_employees)}\n"
            f"Existing Attendance: {len(existing_attendance)}\n"
            f"Marked Absent: {absent_count}\n"
            f"Submitted: {submitted_count}\n"
            f"Errors: {error_count}"
        )

    except Exception as e:
        frappe.log_error(
            message=f"Error in auto mark absent job: {str(e)}",
            title="Auto Mark Absent Job Failed"
        )