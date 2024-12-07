import frappe
from frappe import _
from typing import Dict, Any, Optional

def handle_error_response(error: Exception, error_message: str) -> Dict[str, Any]:
    """Standard error response handler"""
    frappe.log_error(f"{error_message}: {str(error)}")
    return {
        "status": "error",
        "message": _(error_message),
        "error": str(error),
        "http_status_code": 500
    }

@frappe.whitelist()
def get_max_table_row_id(table_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the maximum custom_table_row_id for a given table_name
    Args:
        table_name: The name of the table to query
    Returns:
        Dict containing status, message and data
    """
    try:
        if not table_name:
            return {
                "status": "error",
                "message": _("Table name is required"),
                "http_status_code": 400
            }
        
        # Direct SQL query to get the maximum ID
        result = frappe.db.sql("""
            SELECT CAST(custom_table_row_id AS UNSIGNED) as row_id 
            FROM `tabAttendance`
            WHERE custom_table_name = %s 
            AND custom_table_row_id IS NOT NULL
            AND custom_table_row_id != ''
            ORDER BY CAST(custom_table_row_id AS UNSIGNED) DESC
            LIMIT 1
        """, (table_name))
        
        max_id = result[0][0] if result else 0
        
        return {
            "status": "success",
            "message": "Maximum row ID retrieved successfully",
            "data": {
                "max_id": max_id,
                "table_name": table_name
            }
        }
        
    except Exception as e:
        return handle_error_response(e, "Error retrieving maximum row ID")

@frappe.whitelist()
def create_attendance() -> Dict[str, Any]:
    """
    Create a new attendance record and submit it
    Request body should contain attendance details
    Returns:
        Dict containing status, message and data
    """
    try:
        if not frappe.request.json:
            return {
                "status": "error",
                "message": _("Request body is required"),
                "http_status_code": 400
            }
        
        attendance_data = frappe.request.json
        
        # Validate required fields
        required_fields = ["naming_series", "employee", "employee_name", "status", 
                         "attendance_date", "company"]
        missing_fields = [field for field in required_fields 
                         if not attendance_data.get(field)]
        
        if missing_fields:
            return {
                "status": "error",
                "message": _("Missing required fields: {}").format(", ".join(missing_fields)),
                "http_status_code": 400
            }
        
        # Check if attendance already exists
        existing_attendance = frappe.db.exists("Attendance", {
            "employee": attendance_data.get("employee"),
            "attendance_date": attendance_data.get("attendance_date"),
            "docstatus": ["!=", 2]  # Not cancelled
        })
        
        if existing_attendance:
            return {
                "status": "error",
                "message": _("Attendance already exists for this employee on this date"),
                "http_status_code": 400
            }
        
        # Create new attendance record
        attendance = frappe.get_doc({
            "doctype": "Attendance",
            **attendance_data
        })
        
        attendance.insert()
        attendance.submit()  # Submit the document
        
        return {
            "status": "success",
            "message": _("Attendance created and submitted successfully"),
            "data": {
                "name": attendance.name,
                "employee": attendance.employee,
                "attendance_date": attendance.attendance_date,
                "docstatus": attendance.docstatus  # Will be 1 for submitted
            }
        }
        
    except Exception as e:
        return handle_error_response(e, "Error creating attendance record")


@frappe.whitelist(methods=["GET"])
def get_total_attendance_count_and_leave_count() -> Dict[str, Any]:
    """
    Get total attendance count for current month and remaining leave count for logged-in user
    Returns:
        Dict containing status, message and data with attendance and leave counts
    """
    try:
        # Check if user is linked to an employee
        employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if not employee:
            return {
                "status": "error",
                "message": _("No employee record found for current user"),
                "http_status_code": 400
            }
        
        # Get current month's attendance count
        month_start = frappe.utils.get_first_day(frappe.utils.nowdate())
        month_end = frappe.utils.get_last_day(frappe.utils.nowdate())
        
        attendance_count = frappe.db.count("Attendance", {
            "employee": employee,
            "attendance_date": ["between", (month_start, month_end)]    ,
            "status": "Present",
            "docstatus": 1
        })

        # Get today's attendance details
        today = frappe.utils.nowdate()
        today_attendance = frappe.db.get_value(
            "Attendance",
            {
                "employee": employee,
                "attendance_date": today,
                "status": "Present",
                "docstatus": 1
            },
            ["name", "employee", "employee_name", "attendance_date", "status", 
             "in_time", "out_time", "working_hours", "late_entry", "early_exit"],
            as_dict=True
        )
        
        # Replace HTTP request with direct function import
        from hrms.hr.doctype.leave_application.leave_application import get_leave_details
        
        leave_data = get_leave_details(employee, frappe.utils.nowdate())
        
        # Calculate total remaining leaves across all leave types
        total_remaining_leaves = sum(
            leave_type["remaining_leaves"]
            for leave_type in leave_data.get("leave_allocation", {}).values()
        )
        
        # Set default values
        attendance_count = attendance_count if attendance_count is not None else 0
        total_remaining_leaves = total_remaining_leaves if 'total_remaining_leaves' in locals() else 0

        return {
            "status": "success",
            "message": "Data retrieved successfully",
            "data": {
                "employee": employee,
                "current_month_attendance_count": attendance_count,
                "total_remaining_leaves": total_remaining_leaves,
                "today_attendance": today_attendance
            }
        }
        
    except Exception as e:
        return handle_error_response(e, "Error retrieving attendance and leave counts")
    
@frappe.whitelist(methods=["POST"])
def get_today_attendance() -> Dict[str, Any]:
    """
    Get today's attendance details for all the employees
    Returns:
        Dict containing status, message and data with today's attendance details
    """
    try:
        today = frappe.utils.nowdate()
        
        # Get detailed attendance records including essential fields
        attendance_details = frappe.get_all(
            "Attendance",
            filters={
                "attendance_date": today,
                "docstatus": 1  # Submitted documents
            }
        )

        if not attendance_details:
            return {
                "status": "success",
                "message": _("No attendance records found for today"),
                "data": []
            }

        # Enhance each attendance record with department and designation
        for record in attendance_details:
            employee_details = frappe.db.get_value(
                "Employee",
                record.employee,
                ["department", "designation"],
                as_dict=True
            )
            record.update(employee_details)

        return {
            "status": "success",
            "message": _("Attendance data retrieved successfully"),
            "data": attendance_details,
            "total_records": len(attendance_details)
        }
    
    except Exception as e:
        return handle_error_response(e, "Error retrieving today's attendance details")

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