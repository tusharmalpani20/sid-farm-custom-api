import frappe
from frappe import _
from typing import Dict, Any
from .attendance_api import verify_dp_token, handle_error_response

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_field_options() -> Dict[str, Any]:
    """
    Dynamically returns all select field options for Farmer Details and Visit Tracker
    Required header: Authorization Bearer token
    """
    try:
        # Get the authorization header
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result

        doctypes = {
            "farmer_details": "Farmer Details",
            "visit_tracker": "Visit Tracker"
        }
        
        options = {}
        
        for key, doctype in doctypes.items():
            try:
                meta = frappe.get_meta(doctype)
            except Exception as e:
                frappe.local.response['http_status_code'] = 404
                return {
                    "success": False,
                    "status": "error",
                    "message": f"DocType {doctype} not found",
                    "code": "DOCTYPE_NOT_FOUND",
                    "http_status_code": 404
                }

            doctype_options = {}
            
            # Get all fields of type "Select"
            select_fields = [field for field in meta.fields if field.fieldtype == "Select"]
            
            # Extract options for each select field
            for field in select_fields:
                if field.options:
                    # Split options string into list and remove empty strings
                    field_options = [opt for opt in field.options.split('\n') if opt]
                    doctype_options[field.fieldname] = field_options
            
            options[key] = doctype_options

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Options retrieved successfully",
            "code": "OPTIONS_RETRIEVED",
            "data": options,
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving field options")
