import frappe
from frappe import _
from datetime import datetime, timedelta
import random
import requests  # For TextLocal API
import jwt
import urllib.request
import urllib.parse
import json
import pytz

@frappe.whitelist(allow_guest=True)
def send_otp(phone_number):
    try:
        # Standardize and validate phone number
        try:
            phone_number = standardize_phone_number(phone_number)
        except ValueError:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Invalid phone number format. Please enter a valid 10-digit number",
                "code": "INVALID_PHONE",
                "http_status_code": 400
            }

        # Check if employee exists and is active
        employee = frappe.get_value("Employee", 
            filters={
                "cell_number": phone_number,
                "status": "Active"
            },
            fieldname=["name", "employee_name", "cell_number"]
        )
        
        if not employee:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "No active employee found with this number",
                "code": "EMPLOYEE_NOT_FOUND",
                "http_status_code": 400
            }

        # Expire any existing active OTPs by setting expires_at to current IST time
        ist = pytz.timezone('Asia/Kolkata')
        current_ist_time = datetime.now(ist)

        existing_otps = frappe.get_all("OTP",
            filters={
                "phone": phone_number,
                "is_expired": 0,
                "verified_at": None
            },
            fields=["name"]
        )
        
        for otp in existing_otps:
            frappe.db.set_value("OTP", otp.name, {
                "expires_at": current_ist_time,
                "is_expired": 1
            })

        # Generate 4-digit OTP
        otp_code = ''.join(random.choices('0123456789', k=4))
        
        # Create OTP record with IST timing
        otp_doc = frappe.get_doc({
            "doctype": "OTP",
            "phone": phone_number,
            "code": otp_code,
            "send_for": "Delivery Partner Mobile Auth",
            "provider": "Text Local",
            "send_at": current_ist_time,
            "expires_at": current_ist_time + timedelta(minutes=2),
            "is_expired": 0
        })
        otp_doc.insert()

        # Send SMS via TextLocal
        #send_sms_via_textlocal(phone_number, otp_code)

        return {
            "success": True,
            "status": "success",
            "message": "OTP sent successfully",
            "code": "OTP_SENT",
            "http_status_code": 200
        }

    except Exception as e:
        frappe.log_error(str(e), "OTP Send Error")
        frappe.local.response['http_status_code'] = 500
        return {
            "success": False,
            "status": "error",
            "message": "Failed to send OTP",
            "code": "SYSTEM_ERROR",
            "error": str(e),
            "http_status_code": 500
        }

@frappe.whitelist(allow_guest=True)
def verify_otp(phone_number, otp_code):
    try:
        # Validate phone number format
        if not phone_number or len(phone_number) != 10 or not phone_number.isdigit():
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Invalid phone number. Please enter 10 digits",
                "code": "INVALID_PHONE",
                "http_status_code": 400
            }

        # Find valid OTP entry
        otp = frappe.get_value("OTP",
            filters={
                "phone": phone_number,
                "code": otp_code,
                "is_expired": 0,
                "verified_at": None
            },
            fieldname=["name", "expires_at"],
            as_dict=1
        )

        if not otp:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Invalid OTP",
                "code": "INVALID_OTP",
                "http_status_code": 400
            }

        # Check if OTP is expired
        if datetime.now() > frappe.utils.get_datetime(otp.expires_at):
            frappe.db.set_value("OTP", otp.name, "is_expired", 1)
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "OTP has expired",
                "code": "OTP_EXPIRED",
                "http_status_code": 400
            }

        # Mark OTP as verified
        frappe.db.set_value("OTP", otp.name, {
            "verified_at": datetime.now(),
            "is_expired": 0
        })

        # Get employee details
        employee = frappe.get_value("Employee",
            filters={
                "cell_number": phone_number,
                "status": "Active"
            },
            fieldname=["name", "employee_name", "cell_number"],
            as_dict=1
        )

        # Get IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        current_ist_time = datetime.now(ist)

        # 1. Update existing active tokens for this employee to expired
        existing_tokens = frappe.get_all("DP Mobile Token",
            filters={
                "employee": employee.name,
                "status": "Active"
            },
            fields=["name"]
        )
        
        for token in existing_tokens:
            frappe.db.set_value("DP Mobile Token", token.name, {
                "status": "Expired",
                "expires_at": current_ist_time
            })

        # 2. Create new token record with IST timing
        token_doc = frappe.get_doc({
            "doctype": "DP Mobile Token",
            "employee": employee.name,
            "status": "Active",
            "created_at": current_ist_time,
            "expires_at": current_ist_time + timedelta(days=30),
            "last_login": current_ist_time
        })
        token_doc.insert()
        
        # 3. Generate JWT token
        secret_key = frappe.conf.get('jwt_secret_key')
        jwt_payload = {
            'token_id': token_doc.name,
            'employee': employee.name,
            'exp': datetime.timestamp(datetime.now() + timedelta(days=30))
        }
        jwt_token = jwt.encode(jwt_payload, secret_key, algorithm="HS256")

        return {
            "success": True,
            "status": "success",
            "message": "OTP verified successfully",
            "code": "OTP_VERIFIED",
            "employee": employee,
            "token": jwt_token,
            "http_status_code": 200
        }

    except Exception as e:
        frappe.log_error(str(e), "OTP Verification Error")
        frappe.local.response['http_status_code'] = 500
        return {
            "success": False,
            "status": "error",
            "message": "Failed to verify OTP",
            "code": "SYSTEM_ERROR",
            "error": str(e),
            "http_status_code": 500
        }

@frappe.whitelist(allow_guest=True)
def resend_otp(phone_number):
    try:
        # First verify if employee exists 
        employee = frappe.get_value("Employee",
            filters={
                "cell_number": phone_number,
                "status": "Active"
            },
            fieldname=["name"]
        )
        
        if not employee:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "No active employee found with this number",
                "code": "EMPLOYEE_NOT_FOUND",
                "http_status_code": 400
            }

        # Expire any existing active OTPs
        existing_otps = frappe.get_all("OTP",
            filters={
                "phone": phone_number,
                "is_expired": 0,
                "verified_at": None
            },
            fields=["name"]
        )
        
        for otp in existing_otps:
            frappe.db.set_value("OTP", otp.name, "is_expired", 1)

        # Generate and send new OTP (reuse send_otp logic)
        return send_otp(phone_number)

    except Exception as e:  
        frappe.log_error(str(e), "OTP Resend Error")
        frappe.local.response['http_status_code'] = 500
        return {
            "success": False,
            "status": "error",
            "message": "Failed to resend OTP",
            "code": "SYSTEM_ERROR",
            "error": str(e),
            "http_status_code": 500
        }

def standardize_phone_number(phone_number):
    """
    Standardizes phone number to 10 digits by:
    1. Removing any '+' symbols
    2. Removing leading '91' or '0'
    3. Ensuring exactly 10 digits remain
    """
    # Remove any spaces or special characters
    cleaned = ''.join(filter(str.isdigit, str(phone_number)))
    
    # Remove leading '91' if present
    if cleaned.startswith('91') and len(cleaned) > 10:
        cleaned = cleaned[2:]
    
    # Remove leading '0' if present
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]
    
    # Validate final number
    if len(cleaned) != 10:
        raise ValueError(f"Invalid phone number format: {phone_number}")
        
    return cleaned

def send_sms_via_textlocal(phone_number, otp_code):
    try:
        # Get API key from Frappe configuration
        api_key = frappe.conf.get('textlocal_api_key')
        if not api_key:
            frappe.log_error("TextLocal API key not configured", "SMS Error")
            return False

        # Standardize and format phone number
        try:
            standardized_number = standardize_phone_number(phone_number)
            formatted_number = f"91{standardized_number}"
        except ValueError as e:
            frappe.log_error(f"Phone number standardization failed: {str(e)}", "SMS Error")
            return False

        # Prepare data for API request
        data = {
            'apikey': api_key,
            'numbers': formatted_number,
            'sender': frappe.conf.get('textlocal_sender_id', 'SIDOTP'),
            'template_id': "1407162867250922316",
            'test': False,
            'message': f"{otp_code} is your 4 digit Sid's farm OTP for log in.\n\n {otp_code}\nSid's Farm."
        }

        # Encode data for POST request
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')

        # Make API request
        request = urllib.request.Request("https://api.textlocal.in/send/?")
        response = urllib.request.urlopen(request, encoded_data)
        response_data = response.read().decode('utf-8')
        
        # Parse response
        json_response = frappe.parse_json(response_data)
        
        if json_response.get('status') == 'success':
            return True
        else:
            frappe.log_error(f"TextLocal API Error: {response_data}", "SMS Error")
            return False

    except Exception as e:
        frappe.log_error(f"Failed to send SMS via TextLocal: {str(e)}", "SMS Error")
        return False
