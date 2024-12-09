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
            frappe.response.status_code = result.get("http_status_code", 500)
            return result
        
        employee = result["employee"]
        
        # Get request data
        if not frappe.request.json:
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": "Request body is required",
                "http_status_code": 400
            }
        
        data = frappe.request.json
        required_fields = ["latitude", "longitude", "accuracy", "recorded_at"]
        
        # Validate required fields
        for field in required_fields:
            if field not in data:
                frappe.response.status_code = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": f"{field.replace('_', ' ').title()} is required",
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
                }, "name")
            
            if not attendance:
                frappe.response.status_code = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": "No approved attendance found for today",
                    "http_status_code": 400
                }
            
            # Create route tracking entry
            route_tracking = frappe.get_doc({
                "doctype": "Route Tracking",
                "attendance": attendance,
                "latitude": float(data["latitude"]),
                "longitude": float(data["longitude"]),
                "accuracy": float(data["accuracy"]),
                "recorded_at": data.get("recorded_at") or frappe.utils.now_datetime()
            })
            
            route_tracking.insert()
            
            frappe.response.status_code = 201
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
            frappe.response.status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": str(e),
                "http_status_code": 400
            }
            
    except Exception as e:
        frappe.response.status_code = 500
        return handle_error_response(e, "Error recording location")
