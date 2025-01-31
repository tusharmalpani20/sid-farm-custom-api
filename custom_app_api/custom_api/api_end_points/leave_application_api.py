import frappe
from frappe import _
from typing import Dict, Any, List
from .attendance_api import verify_dp_token, handle_error_response

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_leave_application() -> Dict[str, Any]:
    """
    Create a new Leave Application
    Required fields in request body:
    {
        "from_date": "YYYY-MM-DD",
        "to_date": "YYYY-MM-DD",
        "leave_type": "Leave Type",
        "description": "Reason for leave"
    }
    """
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 401)
            return result
        
        employee = result["employee"]
        
        # Get request data
        if not frappe.request.json:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Request body is required",
                "code": "REQUEST_BODY_REQUIRED",
                "http_status_code": 400
            }
        
        data = frappe.request.json
        required_fields = ["from_date", "to_date", "leave_type", "description"]
        
        # Validate required fields
        for field in required_fields:
            if not data.get(field):
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": _(f"{field.replace('_', ' ').title()} is required"),
                    "code": "REQUEST_BODY_REQUIRED",
                    "http_status_code": 400
                }
        
        try:
            # Create Leave Application
            leave_application = frappe.get_doc({
                "doctype": "Leave Application",
                "employee": employee,
                "leave_type": data["leave_type"],
                "from_date": data["from_date"],
                "to_date": data["to_date"],
                "description": data["description"],
                "status": "Open",
                "posting_date": frappe.utils.today()
            })
            
            leave_application.insert()
            frappe.local.response['http_status_code'] = 201
            return {
                "success": True,
                "status": "success",
                "message": "Leave application created successfully",
                "code": "LEAVE_APPLICATION_CREATED",
                "data": {
                    "name": leave_application.name,
                    "from_date": leave_application.from_date,
                    "to_date": leave_application.to_date,
                    "total_leave_days": leave_application.total_leave_days,
                    "leave_balance": leave_application.leave_balance
                },
                "http_status_code": 201
            }
            
        except frappe.ValidationError as e:
            # Set the status code before returning the response
            frappe.local.response.http_status_code = 400
            return {
                "success": False,
                "status": "error",
                "message": str(e),
                "code": "INVALID_LEAVE_APPLICATION",
                "http_status_code": 400
            }
            
    except Exception as e:
        frappe.local.response.http_status_code = 500
        return handle_error_response(e, "Error creating leave application")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_leave_types() -> Dict[str, Any]:
    """
    Get all active leave types available for the employee
    """
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 401)
            return result
        
        employee = result["employee"]
        
        # Get all active leave types
        leave_types = frappe.get_all(
            "Leave Type",
            fields=[
                "name",
                "max_continuous_days_allowed",
                "is_carry_forward",
                "is_earned_leave",
                "allow_negative"
            ],
            filters={
                "docstatus": 0  # Active leave types
            }
        )
        
        # Import get_leave_details function
        from hrms.hr.doctype.leave_application.leave_application import get_leave_details
        
        # Get detailed leave information including allocations and used leaves
        leave_details = get_leave_details(employee, frappe.utils.today())
        
        # Format response
        formatted_types = []
        for leave_type in leave_types:
            leave_allocation = leave_details.get("leave_allocation", {}).get(leave_type.name, {})
            
            formatted_types.append({
                "leave_type": leave_type.name,
                "max_continuous_days": leave_type.max_continuous_days_allowed,
                "can_carry_forward": leave_type.is_carry_forward,
                "is_earned_leave": leave_type.is_earned_leave,
                "allow_negative": leave_type.allow_negative,
                "total_allocated": leave_allocation.get("total_leaves", 0),
                "used_leaves": leave_allocation.get("leaves_taken", 0),
                "pending_leaves": leave_allocation.get("pending_leaves", 0),
                "balance": leave_allocation.get("remaining_leaves", 0)
            })

        return {
            "success": True,
            "status": "success",
            "message": "Leave types retrieved successfully",
            "code": "LEAVE_TYPES_RETRIEVED",
            "data": {
                "leave_types": formatted_types
            },
            "http_status_code": 200
        }
        
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error fetching leave types")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_pending_leave_applications() -> Dict[str, Any]:
    """
    Get all pending (Open) leave applications for the authenticated employee
    """
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 401)
            return result
        
        employee = result["employee"]
        
        from frappe.utils import add_days, today
        thirty_days_ago = add_days(today(), -30)

        # Get both open leaves and recent submissions
        leave_applications = frappe.get_all(
            "Leave Application",
            fields=[
                "name",
                "leave_type",
                "from_date",
                "to_date",
                "total_leave_days",
                "description",
                "posting_date",
                "status",  # Added status field
                "leave_approver_name",
                "leave_approver"
            ],
            filters=[
                [
                    "employee", "=", employee
                ],
                [
                    "docstatus", "=", 1  # 1 means submitted
                ],
                [
                    "posting_date", ">=", thirty_days_ago
                ]
            ],
            order_by="posting_date desc"
        )

        # Get open status applications (regardless of date)
        open_applications = frappe.get_all(
            "Leave Application",
            fields=[
                "name",
                "leave_type",
                "from_date",
                "to_date",
                "total_leave_days",
                "description",
                "posting_date",
                "status",  # Added status field
                "leave_approver_name",
                "leave_approver"
            ],
            filters={
                "employee": employee,
                "status": "Open",
                "docstatus": 0  # 0 means draft/open
            },
            order_by="posting_date desc"
        )

        # Merge both lists and remove duplicates based on 'name'
        seen_names = set()
        merged_applications = []
        
        for app in open_applications + leave_applications:
            if app.name not in seen_names:
                seen_names.add(app.name)
                merged_applications.append(app)

        return {
            "success": True,
            "status": "success",
            "message": "Leave applications retrieved successfully",
            "code": "LEAVE_APPLICATIONS_RETRIEVED",
            "data": {
                "leave_applications": merged_applications
            },
            "http_status_code": 200
        }
        
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error fetching leave applications")

