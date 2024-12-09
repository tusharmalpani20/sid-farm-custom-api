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

def verify_dp_token(headers: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify the JWT token from headers and handle Frappe authentication
    Returns:
        Tuple of (is_valid, response_dict)
    """
    try:
        # Extract token from headers
        auth_header = headers.get('Auth-Token')
        if not auth_header or not auth_header.startswith('Bearer '):
            return False, {
                "status": "error",
                "message": "Missing or invalid authorization header",
                "http_status_code": 401
            }
        
        auth_token = auth_header.split(' ')[1]
        
        # Decode JWT token
        secret_key = frappe.conf.get('jwt_secret_key')
        decoded_token = jwt.decode(auth_token, secret_key, algorithms=["HS256"])
        
        # Get token record
        token_record = frappe.get_doc("DP Mobile Token", decoded_token.get('token_id'))
        
        # Check if token exists and is active
        if not token_record or token_record.status != "Active":
            return False, {
                "status": "error",
                "message": "Invalid or inactive token",
                "http_status_code": 401
            }
        # Check if token has expired
        if datetime.now() > frappe.utils.get_datetime(token_record.expires_at):
            # Update token status to expired
            token_record.status = "Expired"
            token_record.save()
            return False, {
                "status": "error",
                "message": "Token has expired",
                "http_status_code": 401
            }
        
        # Check if employee is still active
        employee_status = frappe.db.get_value("Employee", token_record.employee, "status")
        if employee_status != "Active":
            return False, {
                "status": "error",
                "message": "Employee is not active",
                "http_status_code": 401
            }

        # Update last_login time
        token_record.last_login = frappe.utils.now()
        token_record.save()
        
        # Handle Frappe authentication
        # api_key = frappe.conf.get('api_key')
        # api_secret = frappe.conf.get('api_secret')
        
        # if api_key and api_secret:
        #     frappe.session.user = "Administrator"
        frappe.session.user = "Administrator"
        #frappe.session.user = "dp_app_api@api.com"
        
        return True, {
            "employee": token_record.employee,
            "user": frappe.session.user,
            "name": token_record.name,
            "token": auth_token
        }
        
    except jwt.ExpiredSignatureError:
        return False, {
            "status": "error",
            "message": "Token has expired",
            "http_status_code": 401
        }
    except jwt.InvalidTokenError:
        return False, {
            "status": "error",
            "message": "Invalid token",
            "http_status_code": 401
        }
    except Exception as e:
        return False, handle_error_response(e, "Error verifying token")


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
            frappe.response.status_code = 400
            return {
                "status": "error",
                "message": "Missing required fields: {}".format(", ".join(missing_fields)),
                "http_status_code": 400
            }
        # Check if attendance already exists
        existing_attendance = frappe.db.exists("Attendance", {
            "employee": attendance_data.get("employee"),
            "attendance_date": attendance_data.get("attendance_date"),
            "docstatus": ["!=", 2]  # Not cancelled
        })
        
        if existing_attendance:
            frappe.response.status_code = 400
            return {
                "status": "error",
                "message": "Attendance already exists for this employee on this date",
                "http_status_code": 400
            }
        
        # Get employee details and validate status
        employee = frappe.get_doc("Employee", attendance_data.get("employee"))
        if not employee or employee.status != "Active":
            frappe.response.status_code = 400
            return {
                "status": "error",
                "message": "Employee is not active or does not exist",
                "http_status_code": 400
            }

        # Add custom_route and fetch total_delivery from Route
        if employee.custom_route:
            attendance_data["custom_route"] = employee.custom_route
            
            # Get total_delivery from Route doctype
            route_total_delivery = frappe.db.get_value(
                "Route",
                employee.custom_route,
                "total_delivery"
            )
            
            if route_total_delivery:
                attendance_data["custom_total_deliveries"] = route_total_delivery
        
        # Create new attendance record
        attendance = frappe.get_doc({
            "doctype": "Attendance",
            **attendance_data
        })
        
        attendance.insert()
        # Don't submit the document here anymore
        # attendance.submit()  # Removed
        
        return {
            "status": "success",
            "message": "Attendance created successfully",
            "data": {
                "name": attendance.name,
                "employee": attendance.employee,
                "attendance_date": attendance.attendance_date,
                "custom_route": attendance.custom_route,
                "docstatus": attendance.docstatus
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
                "docstatus": ["in", [0, 1]]  # Modified to include draft documents
            },
            ["name", "employee", "employee_name", "attendance_date", "status", 
             "in_time", "out_time", "working_hours", "late_entry", "early_exit", "custom_attendance_marked_at" , "custom_mobile_punch_in_at", "custom_mobile_punch_out_at","custom_total_deliveries"],
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
        
    
@frappe.whitelist(allow_guest=True, methods=["POST"])
def mobile_punch_in() -> Dict[str, Any]:
    """Update mobile punch in time for an employee's attendance"""
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        
        if not is_valid:
            frappe.response.status_code = result.get("http_status_code", 500)
            return result

        if not frappe.request.json:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": "Request body is required",
                "http_status_code": 400
            }

        data = frappe.request.json
        employee = result["employee"]
        
        # Validate punch in time
        punch_in = data.get("custom_mobile_punch_in_at")
        if not punch_in:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": "Punch in time is required",
                "http_status_code": 400
            }
            
        # Convert string to datetime object
        try:
            punch_in_dt = frappe.utils.get_datetime(punch_in)
        except Exception:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": "Invalid datetime format. Use YYYY-MM-DD HH:MM:SS",
                "http_status_code": 400
            }
            
        # Get attendance for the day
        attendance_date = punch_in_dt.date()
        attendance = frappe.db.get_value(
            "Attendance",
            {
                "employee": employee,
                "attendance_date": attendance_date,
                "status": "Present",
                "docstatus": ["in", [0, 1]]
            },
            ["name", "docstatus"],
            as_dict=True
        )
        
        if not attendance:
            frappe.response.status_code = 404
            return {
                "success": False,
                "status": "error",
                "message": "No attendance record found for the date",
                "http_status_code": 404
            }
            
        # Update attendance
        attendance_doc = frappe.get_doc("Attendance", attendance.name)
        
        # If document is already submitted, cancel it first
        if attendance_doc.docstatus == 1:
            attendance_doc.cancel()
            attendance_doc.reload()
        
        attendance_doc.custom_mobile_punch_in_at = punch_in
        attendance_doc.save(ignore_permissions=True)
        
        return {
            "success": True,
            "status": "success",
            "message": "Punch in time updated successfully",
            "data": {
                "name": attendance_doc.name,
                "employee": attendance_doc.employee,
                "attendance_date": attendance_doc.attendance_date,
                "custom_mobile_punch_in_at": attendance_doc.custom_mobile_punch_in_at,
                "docstatus": attendance_doc.docstatus
            }
        }
        
    except Exception as e:
        return handle_error_response(e, "Error updating punch in time")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def mobile_punch_out() -> Dict[str, Any]:
    """Update mobile punch out time for an employee's attendance"""
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        
        if not is_valid:
            frappe.response.status_code = result.get("http_status_code", 500)
            return result

        if not frappe.request.json:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": "Request body is required",
                "http_status_code": 400
            }

        data = frappe.request.json
        employee = result["employee"]
        
        # Validate punch out time
        punch_out = data.get("custom_mobile_punch_out_at")
        if not punch_out:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": "Punch out time is required",
                "http_status_code": 400
            }
            
        # Convert string to datetime object
        try:
            punch_out_dt = frappe.utils.get_datetime(punch_out)
        except Exception:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": "Invalid datetime format. Use YYYY-MM-DD HH:MM:SS",
                "http_status_code": 400
            }
            
        # Get attendance for the day
        attendance_date = punch_out_dt.date()
        attendance = frappe.db.get_value(
            "Attendance",
            {
                "employee": employee,
                "attendance_date": attendance_date,
                "status": "Present",
                "docstatus": ["in", [0, 1]]
            },
            ["name", "docstatus", "custom_mobile_punch_in_at", "custom_total_deliveries"],
            as_dict=True
        )
        
        if not attendance:
            frappe.response.status_code = 404
            return {
                "success": False,
                "status": "error",
                "message": "No attendance record found for the date",
                "http_status_code": 404
            }
        
        # Validate punch out is after punch in
        punch_in_dt = frappe.utils.get_datetime(attendance.custom_mobile_punch_in_at)
        if punch_in_dt >= punch_out_dt:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": "Punch out time must be after punch in time",
                "http_status_code": 400
            }

        # Check delivery records count
        actual_delivery_count = frappe.db.count(
            "Delivery Record",
            filters={
                "attendance": attendance.name,
                "docstatus": 1  # Only count submitted delivery records
            }
        )

        expected_deliveries = attendance.custom_total_deliveries or 0

        if actual_delivery_count != expected_deliveries:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": f"Cannot punch out. Expected {expected_deliveries} deliveries but found {actual_delivery_count}",
                "data": {
                    "expected_deliveries": expected_deliveries,
                    "actual_deliveries": actual_delivery_count
                },
                "http_status_code": 400
            }
            
        # Update attendance
        attendance_doc = frappe.get_doc("Attendance", attendance.name)
        
        # If document is already submitted, cancel it first
        if attendance_doc.docstatus == 1:
            attendance_doc.cancel()
            attendance_doc.reload()
        
        attendance_doc.custom_mobile_punch_out_at = punch_out
        attendance_doc.docstatus = 1  # Submit when punch out is provided
        attendance_doc.save(ignore_permissions=True)
        
        return {
            "success": True,
            "status": "success",
            "message": "Punch out time updated successfully",
            "data": {
                "name": attendance_doc.name,
                "employee": attendance_doc.employee,
                "attendance_date": attendance_doc.attendance_date,
                "custom_mobile_punch_in_at": attendance_doc.custom_mobile_punch_in_at,
                "custom_mobile_punch_out_at": attendance_doc.custom_mobile_punch_out_at,
                "custom_total_deliveries": attendance_doc.custom_total_deliveries,
                "actual_deliveries": actual_delivery_count,
                "docstatus": attendance_doc.docstatus
            }
        }
        
    except Exception as e:
        return handle_error_response(e, "Error updating punch out time")

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