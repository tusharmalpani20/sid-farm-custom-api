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
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.log_error(
                title="Token Verification Failed",
                message=f"Invalid token: {result}"
            )
            # frappe.local.response['http_status_code'] = result.get("http_status_code", 401)
            # return result
            # We have commented the above code and added the below code to return the error message, since we want the recording to stop
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Location recording stopped - You have already punched out for today",
                "code": "STOP_LOCATION_RECORDING",
                "http_status_code": 400
            }
            
        
        employee = result["employee"]
        
        # Get request data
        if not frappe.request.json:
            frappe.log_error(
                title="Missing Request Body",
                message="Request body is missing in location recording"
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
            # Get today's attendance
            attendance = frappe.get_value("Attendance", 
                {
                    "employee": employee,
                    "attendance_date": frappe.utils.today(),
                    "docstatus": ["in", [0, 1]],
                    "status": "Present"
                }, ["name", "custom_mobile_punch_out_at"])
            
            if not attendance:
                frappe.log_error(
                    title="No Attendance Found",
                    message=f"No approved attendance found for employee {employee} on {frappe.utils.today()}"
                )
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": "No approved attendance found for today",
                    "code": "NO_APPROVED_ATTENDANCE_FOUND_FOR_TODAY",
                    "http_status_code": 400
                }

            attendance_name, punch_out_time = attendance  # Unpack the tuple

            # Check if employee has punched out
            if punch_out_time:
                frappe.log_error(
                    title="Employee Already Punched Out",
                    message=f"Employee {employee} has already punched out on {frappe.utils.today()}"
                )
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": "Location recording stopped - You have already punched out for today",
                    "code": "STOP_LOCATION_RECORDING",
                    "http_status_code": 400
                }
            
            # Check for recent recordings in the last 10 seconds
            last_recording = frappe.get_value("Route Tracking",
                {
                    "employee": employee,
                    "recorded_at": [">=", frappe.utils.add_to_date(frappe.utils.now_datetime(), seconds=-9)]
                }, "name")
            
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
            frappe.log_error(
                title="Validation Error in Location Recording",
                message=f"Error for employee {employee}: {str(e)}"
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
        frappe.log_error(
            title="Location Recording Error",
            message=f"Unexpected error: {str(e)}\nTraceback: {frappe.get_traceback()}"
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