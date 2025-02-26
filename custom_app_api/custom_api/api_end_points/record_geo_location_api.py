import frappe
from frappe import _
from typing import Dict, Any
from .attendance_api import verify_dp_token, handle_error_response

@frappe.whitelist(allow_guest=True, methods=["POST"])
def record_location() -> Dict[str, Any]:
    """
    Record employee location
    Required fields in request body:
    {
        "latitude": float,
        "longitude": float,
        "accuracy": float,
        "recorded_at": "YYYY-MM-DD HH:MM:SS"
    }
    """
    try:
        print("Starting location recording process")
        # Verify token and authenticate
        print(f"Request Headers: {frappe.request.headers}")
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            print(f"Token Verification Failed - Result: {result}")
            print(f"Headers: {frappe.request.headers}")
            frappe.log_error(
                title="Token Verification Failed",
                message=f"""
                Invalid token details:
                Result: {result}
                Headers: {frappe.request.headers}
                Request Data: {frappe.request.json if frappe.request.json else 'No data'}
                """
            )
            # frappe.local.response['http_status_code'] = result.get("http_status_code", 401)
            # return result
            # We have commented the above code and added the below code to return the error message, since we want the recording to stop
            frappe.local.response['http_status_code'] = 401
            return {
                "success": False,
                "status": "error",
                "message": "Location recording stopped - You have already punched out for today",
                "code": "STOP_LOCATION_RECORDING",
                "code_token": "INVALID_TOKEN",
                "http_status_code": 401
            }
            
        
        employee = result["employee"]
        print(f"Processing request for employee: {employee}")
        
        # Get request data
        if not frappe.request.json:
            print("Request body is missing")
            frappe.log_error(
                title="Missing Request Body",
                message=f"""
                Request details:
                Headers: {frappe.request.headers}
                Employee: {employee}
                Method: {frappe.request.method}
                Path: {frappe.request.path}
                """
            )
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Request body is required",
                "code": "REQUEST_BODY_REQUIRED",
                "http_status_code": 400
            }
        
        data = frappe.request.json
        print(f"Request data received: {data}")
        required_fields = ["latitude", "longitude", "accuracy", "recorded_at"]
        
        # Validate required fields
        for field in required_fields:
            if field not in data:
                frappe.log_error(
                    title="Missing Required Field",
                    message=f"Missing field '{field}' in location recording request for employee {employee}"
                )
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": f"{field.replace('_', ' ').title()} is required",
                    "code": "REQUEST_BODY_REQUIRED",
                    "http_status_code": 400
                }
        
        try:
            print(f"Fetching attendance for employee {employee} on {frappe.utils.today()}")
            # Get today's attendance
            attendance = frappe.get_value("Attendance", 
                {
                    "employee": employee,
                    "attendance_date": frappe.utils.today(),
                    "docstatus": ["in", [0, 1]],
                    "status": "Present"
                }, ["name", "custom_mobile_punch_out_at"])
            
            print(f"Attendance record found: {attendance}")
            
            if not attendance:
                print(f"No attendance found for employee {employee}")
                frappe.log_error(
                    title="No Attendance Found",
                    message=f"""
                    Details:
                    Employee: {employee}
                    Date: {frappe.utils.today()}
                    Request Data: {data}
                    Headers: {frappe.request.headers}
                    """
                )
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": "No approved attendance found for today",
                    "code": "NO_APPROVED_ATTENDANCE_FOUND_FOR_TODAY",
                    "http_status_code": 400
                }

            attendance_name, punch_out_time = attendance
            print(f"Attendance name: {attendance_name}, Punch out time: {punch_out_time}")

            # Check if employee has punched out
            if punch_out_time:
                print(f"Employee {employee} already punched out at {punch_out_time}")
                frappe.log_error(
                    title="Employee Already Punched Out",
                    message=f"""
                    Details:
                    Employee: {employee}
                    Date: {frappe.utils.today()}
                    Punch Out Time: {punch_out_time}
                    Attendance: {attendance_name}
                    Request Data: {data}
                    """
                )
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": "Location recording stopped - You have already punched out for today",
                    "code": "STOP_LOCATION_RECORDING",
                    "http_status_code": 400
                }
            
            # Check for recent recordings
            current_time = frappe.utils.now_datetime()
            check_time = frappe.utils.add_to_date(current_time, seconds=-9)
            print(f"Checking for recordings between {check_time} and {current_time}")
            
            last_recording = frappe.db.sql("""
                SELECT name 
                FROM `tabRoute Tracking`
                WHERE attendance = %s 
                AND recorded_at >= %s
                LIMIT 1
            """, (attendance_name, check_time), as_dict=0)
            
            last_recording = last_recording[0][0] if last_recording else None
            print(f"Last recording found: {last_recording}")
            
            if last_recording:
                frappe.local.response['http_status_code'] = 200
                return {
                    "success": True,
                    "status": "success",
                    "message": "Location already recorded within last 10 seconds",
                    "data": {
                        "name": last_recording
                    }
                }
            
            # Create route tracking entry
            print(f"Creating new route tracking entry for {employee}")
            route_tracking = frappe.get_doc({
                "doctype": "Route Tracking",
                "attendance": attendance_name,
                "employee": employee,
                "latitude": float(data["latitude"]),
                "longitude": float(data["longitude"]),
                "accuracy": float(data["accuracy"]),
                "recorded_at": data.get("recorded_at") or frappe.utils.now_datetime()
            })
            
            route_tracking.insert()
            print(f"Route tracking entry created: {route_tracking.name}")
            
            frappe.local.response['http_status_code'] = 201
            return {
                "success": True,
                "status": "success",
                "message": "Location recorded successfully",
                "data": {
                    "name": route_tracking.name,
                    "recorded_at": route_tracking.recorded_at
                }
            }
            
        except frappe.ValidationError as e:
            print(f"Validation error occurred: {str(e)}")
            frappe.log_error(
                title="Validation Error in Location Recording",
                message=f"""
                Error details:
                Employee: {employee}
                Error: {str(e)}
                Request Data: {data}
                Traceback: {frappe.get_traceback()}
                """
            )
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": str(e),
                "code": "REQUEST_BODY_REQUIRED",
                "http_status_code": 400
            }
            
    except Exception as e:
        print(f"Unexpected error occurred: {str(e)}")
        frappe.log_error(
            title="Location Recording Error",
            message=f"""
            Unexpected error details:
            Error: {str(e)}
            Headers: {frappe.request.headers}
            Request Data: {frappe.request.json if frappe.request.json else 'No data'}
            Traceback: {frappe.get_traceback()}
            """
        )
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error recording location")


@frappe.whitelist()
def get_unique_route_tracking(attendance):

    # ROUND(latitude, 4) as latitude,
    # ROUND(longitude, 4) as longitude,
    # recorded_at

    return frappe.db.sql("""
        SELECT 
            latitude,
            longitude
        FROM `tabRoute Tracking`
        WHERE attendance = %s
        ORDER BY recorded_at asc
    """, attendance, as_dict=1)