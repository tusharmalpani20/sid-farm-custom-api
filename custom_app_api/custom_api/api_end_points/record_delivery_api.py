import frappe
from frappe import _
from typing import Dict, Any
import base64
from .attendance_api import verify_dp_token, handle_error_response

@frappe.whitelist(allow_guest=True, methods=["POST"])
def record_delivery() -> Dict[str, Any]:
    """
    Record delivery with location and image
    Required fields in request body:
    {
        "latitude": float,
        "longitude": float,
        "accuracy": float,
        "image": string (base64 encoded image),
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
        required_fields = ["latitude", "longitude", "accuracy", "image", "recorded_at"]
        
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
            
            # Save base64 image as attachment
            try:
                image_string = data["image"]
                # Remove data URL prefix if present
                if image_string.startswith('data:'):
                    image_string = image_string.split('base64,')[1].strip()
                
                try:
                    image_data = base64.b64decode(image_string)
                except Exception as e:
                    frappe.local.response.http_status_code = 400
                    frappe.response.status_code = 400
                    return {
                        "success": False,
                        "status": "error",
                        "message": "Invalid base64 image data. Please check the image format.",
                        "http_status_code": 400,
                        "details": str(e)
                    }

                filename = f"delivery_{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}.jpg"
                
                # Create file attachment
                _file = frappe.get_doc({
                    "doctype": "File",
                    "file_name": filename,
                    "content": image_data,
                    "is_private": 1
                })
                _file.insert()
                
            except Exception as e:
                frappe.response.status_code = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": "Invalid image data",
                    "http_status_code": 400
                }
            
            # Create delivery record
            delivery_record = frappe.get_doc({
                "doctype": "Delivery Records",
                "employee": employee,
                "attendance": attendance,
                "latitude": float(data["latitude"]),
                "longitude": float(data["longitude"]),
                "accuracy": float(data["accuracy"]),
                "image": _file.file_url,
                "recorded_at": data.get("recorded_at") or frappe.utils.now_datetime()
            })
            
            delivery_record.insert()
            delivery_record.submit()
            
            frappe.response.status_code = 201
            return {
                "success": True,
                "status": "success",
                "message": "Delivery recorded successfully",
                "data": {
                    "name": delivery_record.name,
                    "recorded_at": delivery_record.recorded_at,
                    "image_url": delivery_record.image
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
        return handle_error_response(e, "Error recording delivery")
