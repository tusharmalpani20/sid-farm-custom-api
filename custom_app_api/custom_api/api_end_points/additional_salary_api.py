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
                # "docstatus": 0,  # Draft/Pending
                "workflow_state": "Pending",
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
                # "workflow_state"
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
                # "workflow_state": request.workflow_state
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

@frappe.whitelist(methods=["GET"])
def get_additional_salary_records():
    """
    Get Additional Salary records with filters and employee details
    Query Parameters:
    - from_date: YYYY-MM-DD (optional)
    - to_date: YYYY-MM-DD (optional)
    - salary_component: comma-separated string (e.g., "Advance Salary,Referral Bonus")
    - doc_status: 0 or 1
    - workflow_state: comma-separated string (e.g., "Submitted,Approved,Rejected")
    """
    try:
        # Get query parameters
        filters = frappe.request.args
        
        # Set default dates if not provided
        today = datetime.today()
        from_date = filters.get('from_date') or today.replace(day=1).strftime('%Y-%m-%d')
        to_date = filters.get('to_date') or today.replace(day=1, month=today.month+1 if today.month < 12 else 1, 
                                                         year=today.year if today.month < 12 else today.year+1) \
                                               .replace(day=1) - relativedelta(days=1)
        to_date = to_date.strftime('%Y-%m-%d') if isinstance(to_date, date) else to_date

        # Build query conditions and parameters
        conditions = []
        params = {
            "from_date": from_date,
            "to_date": to_date
        }

        # Add base date condition
        date_condition = """
            (payroll_date BETWEEN %(from_date)s AND %(to_date)s)
            OR (
                (from_date <= %(to_date)s)
                AND (to_date >= %(from_date)s)
            )
        """
        conditions.append(date_condition)

        # Add other filters
        if filters.get('doc_status'):
            conditions.append("`docstatus` = %(docstatus)s")
            params["docstatus"] = int(filters.get('doc_status'))

        if filters.get('salary_component'):
            salary_components = [s.strip() for s in filters.get('salary_component').split(',')]
            placeholders = ', '.join([f'%({i})s' for i in range(len(salary_components))])
            conditions.append(f"`salary_component` IN ({placeholders})")
            params.update({str(i): comp for i, comp in enumerate(salary_components)})

        if filters.get('workflow_state'):
            workflow_states = [s.strip() for s in filters.get('workflow_state').split(',')]
            placeholders = ', '.join([f'%(w{i})s' for i in range(len(workflow_states))])
            conditions.append(f"`workflow_state` IN ({placeholders})")
            params.update({f"w{i}": state for i, state in enumerate(workflow_states)})

        # Construct final query
        query = """
            SELECT 
                name, salary_component, custom_reason, custom_total_amount,
                payroll_date, workflow_state, workflow_action_taken_on, 
                employee, amount, custom_pay_in_installment
            FROM `tabAdditional Salary`
            WHERE {conditions}
        """.format(conditions=' AND '.join(conditions))

        # Execute query
        additional_salaries = frappe.db.sql(query, params, as_dict=1)

        # Get employee details and format response
        formatted_records = []
        for salary in additional_salaries:
            employee = frappe.get_value("Employee", salary.employee, [
                "custom_route", "employee_name", "cell_number",
                "bank_name", "custom_beneficiary_name", "bank_ac_no",
                "custom_ifsc_no"
            ], as_dict=1)

            # Use custom_total_amount if it's an installment, otherwise use amount
            display_amount = salary.custom_total_amount if salary.custom_pay_in_installment else salary.amount

            formatted_records.append({
                "id": salary.name,
                "salary_component": salary.salary_component,
                "route_name": employee.custom_route,
                "delivery_executive_name": employee.employee_name,
                "reason": salary.custom_reason,
                "total_amount": display_amount,
                "delivery_phone_number": employee.cell_number,
                "bank_name": employee.bank_name,
                "beneficiary_name": employee.custom_beneficiary_name,
                "bank_ac_no": employee.bank_ac_no,
                "ifsc_no": employee.custom_ifsc_no,
                "payroll_date": salary.payroll_date,
                "action_taken_on": salary.workflow_action_taken_on,
                "status": salary.workflow_state
            })

        return {
            "success": True,
            "status": "success",
            "message": "Additional salary records retrieved successfully",
            "data": {
                "records": formatted_records,
                "total_count": len(formatted_records)
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Error fetching additional salary records'))
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error fetching additional salary records")

