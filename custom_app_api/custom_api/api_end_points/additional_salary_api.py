import frappe
from frappe import _
from typing import Dict, Any
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from .attendance_api import verify_dp_token, handle_error_response

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_advance_salary() -> Dict[str, Any]:
    """
    Create a new Additional Salary record for advance salary
    Request body should contain:
    {
        "custom_total_amount": float,
        "custom_reason": str,
        "custom_pay_in_installment": bool,
        "custom_number_of_installments": int (required if custom_pay_in_installment is True)
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
        
        # Check for pending additional salary requests
        pending_requests = frappe.get_all(
            "Additional Salary",
            filters={
                "employee": employee,
                "salary_component": "Advance Salary",
                "docstatus": 0,
                #"to_date": [">=", date.today()]
            },
            limit=1
        )
        
        if pending_requests:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "You already have a pending advance salary request",
                "code": "PENDING_ADVANCE_SALARY_REQUEST",
                "http_status_code": 400
            }
        
        # Validate required fields
        if not data.get("custom_total_amount"):
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Total amount is required",
                "code": "TOTAL_AMOUNT_REQUIRED",
                "http_status_code": 400
            }
        
        # Validate installment data
        if data.get("custom_pay_in_installment") and not data.get("custom_number_of_installments"):
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Number of installments is required when paying in installments",
                "code": "NUMBER_OF_INSTALLMENTS_REQUIRED",
                "http_status_code": 400
            }
        
        # Calculate dates and amount
        next_month = date.today() + relativedelta(months=1)
        next_month_start = next_month.replace(day=1)
        
        if data.get("custom_pay_in_installment"):
            installments = data["custom_number_of_installments"]
            amount = data["custom_total_amount"] / installments
            to_date = next_month_start + relativedelta(months=installments)
            to_date = to_date - relativedelta(days=1)  # Last day of the final month
        else:
            amount = data["custom_total_amount"]
            # Get the last day of next month
            to_date = next_month_start + relativedelta(months=1) - relativedelta(days=1)
        
        # Create Additional Salary doc
        additional_salary = frappe.get_doc({
            "doctype": "Additional Salary",
            "employee": employee,
            "salary_component": "Advance Salary",
            "amount": amount,
            "company": frappe.get_value("Employee", employee, "company"),
            "is_recurring": 1 if data.get("custom_pay_in_installment") else 0,
            "from_date": next_month_start,
            "to_date": to_date if data.get("custom_pay_in_installment") else None,
            "payroll_date": next_month_start if not data.get("custom_pay_in_installment") else None,
            "custom_total_amount": data["custom_total_amount"],
            "custom_reason": data.get("custom_reason"),
            "custom_pay_in_installment": data.get("custom_pay_in_installment", 0),
            "custom_number_of_installments": data.get("custom_number_of_installments")
        })
        
        additional_salary.insert()
        frappe.local.response['http_status_code'] = 201
        return {
            "success": True,
            "status": "success",
            "message": "Advance salary request created successfully",
            "code": "ADVANCE_SALARY_REQUEST_CREATED",
            "data": {
                "name": additional_salary.name,
                "amount": amount,
                "total_amount": data["custom_total_amount"],
                "installments": data.get("custom_number_of_installments"),
                "from_date": next_month_start,
                "to_date": to_date
            },
            "http_status_code": 201
        }
        
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error creating advance salary request")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_pending_advance_salary() -> Dict[str, Any]:
    """
    Get all pending advance salary requests for the authenticated user
    Returns a list of pending requests with their details
    """
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 401)
            return result
        
        employee = result["employee"]
        
        # Get all pending requests
        pending_requests = frappe.get_all(
            "Additional Salary",
            filters={
                "employee": employee,
                "salary_component": "Advance Salary",
                "docstatus": 0,  # Draft/Pending
                # "to_date": [">=", date.today()]
                # since we are only allowing one request at a time, we don't need to check for to_date
            },
            fields=[
                "name",
                "amount",
                "custom_total_amount",
                "custom_reason",
                "custom_pay_in_installment",
                "custom_number_of_installments",
                "from_date",
                "to_date",
                "creation",
                "modified",
                "workflow_state"
            ]
        )
        
        # Format the response data
        formatted_requests = []
        for request in pending_requests:
            formatted_requests.append({
                "request_id": request.name,
                "amount_per_installment": request.amount,
                "total_amount": request.custom_total_amount,
                "reason": request.custom_reason,
                "is_installment": request.custom_pay_in_installment,
                "number_of_installments": request.custom_number_of_installments,
                "start_date": request.from_date,
                "end_date": request.to_date,
                "created_at": request.creation,
                "last_modified": request.modified,
                "workflow_state": request.workflow_state
            })
        
        return {
            "success": True,
            "status": "success",
            "message": "Pending advance salary requests retrieved successfully",
            "code": "PENDING_ADVANCE_SALARY_REQUESTS_RETRIEVED",
            "data": {
                "additional_salary_list": formatted_requests,
                "total_count": len(formatted_requests)
            },
            "http_status_code": 200
        }
        
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error fetching pending advance salary requests")