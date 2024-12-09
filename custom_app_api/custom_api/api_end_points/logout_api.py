import frappe
from frappe import _
from .attendance_api import verify_dp_token, handle_error_response

@frappe.whitelist(allow_guest=True)
def logout():
    """
    Logout endpoint to invalidate mobile token
    Method: POST
    
    Returns:
        dict: Response with status and message
    """
    try:
        # Get the authorization header
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            return handle_error_response(
                error=Exception(result.get("message", "Invalid token")),
                error_message="Invalid token"
            )
        name = result["name"]

        # Delete the token from DP Mobile Token
        frappe.db.delete("DP Mobile Token", {
            "name": name
        })
        frappe.db.commit()

        return {
            "success": True,
            "status": "success",
            "message": "Logged out successfully",
            "http_status_code": 200
        }

    except Exception as e:
        return handle_error_response(
            error=e,
            error_message="Internal Server Error"
        )
