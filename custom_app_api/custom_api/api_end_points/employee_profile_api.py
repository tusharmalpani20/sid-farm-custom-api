import frappe
from frappe import _
from typing import Dict, Any
import base64
import os
from .attendance_api import verify_dp_token, handle_error_response
import datetime
import pytz

def handle_base64_image(base64_string: str, prefix: str = "file") -> Dict[str, str]:
    """
    Handle base64 image upload
    Args:
        base64_string: Base64 encoded image string
        prefix: Prefix for the file name
    Returns:
        Dict containing file_url and other file details
    """
    try:
        # Remove data URL prefix if present
        if base64_string.startswith('data:'):
            base64_string = base64_string.split('base64,')[1].strip()
        
        try:
            # Decode base64 string
            file_content = base64.b64decode(base64_string)
        except Exception as e:
            frappe.log_error(
                title="Image Processing - Base64 Decode Failed",
                message=f"Error: {str(e)}"
            )
            raise frappe.ValidationError("Invalid base64 image data. Please check the image format.")

        # Generate filename with timestamp
        filename = f"{prefix}_{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}.jpg"
        
        # Create file doc
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": file_content,
            "is_private": 0  # Make it public since it's a visit image
        })
        file_doc.insert()

        return {
            "name": file_doc.name,
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url
        }

    except Exception as e:
        frappe.log_error(
            title="Image Processing Failed",
            message=f"Error: {str(e)}"
        )
        raise

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


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_employee_id_proof(
    custom_aadhaar_card_number: str = None,
    custom_pan: str = None,
    custom_aadhaar_front: str = None,
    custom_aadhaar_back: str = None,
    custom_pan_image: str = None
) -> Dict[str, Any]:
    """
    Update employee documents (Aadhaar and PAN details)
    Only allows updating fields that are currently empty
    Required header: Authorization Bearer token
    """
    frappe.db.begin()
    
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        emp_doc = frappe.get_doc("Employee", employee)
        
        # Dictionary to store updates
        updates = {}
        
        # Handle text fields
        if custom_aadhaar_card_number and not emp_doc.custom_aadhaar_card_number:
            updates['custom_aadhaar_card_number'] = custom_aadhaar_card_number
            
        if custom_pan and not emp_doc.custom_pan:
            updates['custom_pan'] = custom_pan
        
        # Handle image fields
        image_fields = {
            'custom_aadhaar_front': custom_aadhaar_front,
            'custom_aadhaar_back': custom_aadhaar_back,
            'custom_pan_image': custom_pan_image
        }
        
        for field_name, base64_data in image_fields.items():
            if base64_data and not getattr(emp_doc, field_name):
                try:
                    image_result = handle_base64_image(base64_data, prefix=field_name)
                    updates[field_name] = image_result['file_url']
                except Exception as e:
                    frappe.db.rollback()
                    frappe.local.response['http_status_code'] = 400
                    return {
                        "success": False,
                        "status": "error",
                        "message": f"Failed to process {field_name}: {str(e)}",
                        "code": "IMAGE_PROCESSING_FAILED",
                        "http_status_code": 400
                    }
        
        # If there are updates, apply them
        if updates:
            for field, value in updates.items():
                emp_doc.db_set(field, value, update_modified=True)
            
            frappe.db.commit()
            
            frappe.local.response['http_status_code'] = 200
            return {
                "success": True,
                "status": "success",
                "message": "Employee documents updated successfully",
                "code": "DOCUMENTS_UPDATED",
                "data": updates,
                "http_status_code": 200
            }
        else:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "No new documents to update. Fields are already filled.",
                "code": "NO_UPDATES_NEEDED",
                "http_status_code": 400
            }
            
    except Exception as e:
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error updating employee documents")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_employee_vehicle_details(
    custom_vehicle_type: str = None,
    custom_vehicle_registration_number: str = None,
    custom_driving_license_number: str = None,
    custom_driving_license_photo: str = None,
    custom_vehicle_insurance_number: str = None,
    custom_vehicle_insurance_expiry: str = None,
    custom_vehicle_insurance_photo: str = None,
    custom_pollution_certificate_number: str = None,
    custom_pollution_certificate_expiry: str = None,
    custom_pollution_certificate_photo: str = None,
    is_reentry_allowed: bool = False
) -> Dict[str, Any]:
    """
    Update employee vehicle details with conditional re-entry
    Required header: Authorization Bearer token
    """
    frappe.db.begin()
    
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        emp_doc = frappe.get_doc("Employee", employee)
        
        # Dictionary to store updates
        updates = {}
        
        # Define field configurations
        field_config = {
            'custom_vehicle_type': {'type': 'data', 'reentry': True},
            'custom_vehicle_registration_number': {'type': 'data', 'reentry': True},
            'custom_driving_license_number': {'type': 'data', 'reentry': False},
            'custom_driving_license_photo': {'type': 'attach', 'reentry': False},
            'custom_vehicle_insurance_number': {'type': 'data', 'reentry': True},
            'custom_vehicle_insurance_expiry': {'type': 'date', 'reentry': True},
            'custom_vehicle_insurance_photo': {'type': 'attach', 'reentry': True},
            'custom_pollution_certificate_number': {'type': 'data', 'reentry': True},
            'custom_pollution_certificate_expiry': {'type': 'date', 'reentry': True},
            'custom_pollution_certificate_photo': {'type': 'attach', 'reentry': True}
        }

        # Process each field
        for field_name, config in field_config.items():
            field_value = locals().get(field_name)
            if field_value is None:
                continue

            current_value = getattr(emp_doc, field_name)
            
            # Check if update is allowed
            can_update = (
                is_reentry_allowed and config['reentry']  # Re-entry is allowed for this field
                or not current_value  # Field is empty
                or (not config['reentry'] and not current_value)  # No re-entry and field is empty
            )

            if not can_update:
                continue

            if config['type'] == 'attach':
                try:
                    image_result = handle_base64_image(field_value, prefix=field_name)
                    updates[field_name] = image_result['file_url']
                except Exception as e:
                    frappe.db.rollback()
                    frappe.local.response['http_status_code'] = 400
                    return {
                        "success": False,
                        "status": "error",
                        "message": f"Failed to process {field_name}: {str(e)}",
                        "code": "IMAGE_PROCESSING_FAILED",
                        "http_status_code": 400
                    }
            elif config['type'] == 'date':
                try:
                    # Convert date from dd-mm-yyyy to yyyy-mm-dd for storage
                    date_obj = datetime.datetime.strptime(field_value, '%d-%m-%Y')
                    updates[field_name] = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    frappe.db.rollback()
                    frappe.local.response['http_status_code'] = 400
                    return {
                        "success": False,
                        "status": "error",
                        "message": f"Invalid date format for {field_name}. Use dd-mm-yyyy",
                        "code": "INVALID_DATE_FORMAT",
                        "http_status_code": 400
                    }
            else:
                updates[field_name] = field_value

        # If there are updates, apply them
        if updates:
            for field, value in updates.items():
                emp_doc.db_set(field, value, update_modified=True)
            
            frappe.db.commit()
            
            # Convert dates back to dd-mm-yyyy format for response
            response_updates = {}
            for field, value in updates.items():
                if field_config[field]['type'] == 'date':
                    date_obj = datetime.datetime.strptime(value, '%Y-%m-%d')
                    response_updates[field] = date_obj.strftime('%d-%m-%Y')
                else:
                    response_updates[field] = value

            frappe.local.response['http_status_code'] = 200
            return {
                "success": True,
                "status": "success",
                "message": "Vehicle details updated successfully",
                "code": "VEHICLE_DETAILS_UPDATED",
                "data": response_updates,
                "http_status_code": 200
            }
        else:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "No fields to update or updates not allowed",
                "code": "NO_UPDATES_NEEDED",
                "http_status_code": 400
            }
            
    except Exception as e:
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error updating vehicle details")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_employee_uniform_sizes(
    custom_tshirt_size: str = None,
    custom_raincoat_size: str = None,
    custom_trouser_size: str = None,
    custom_shoe_size: str = None,
    custom_helmet_size: str = None,
    is_reentry_allowed: bool = False
) -> Dict[str, Any]:
    """
    Update employee uniform sizes with conditional re-entry
    Required header: Authorization Bearer token
    """
    frappe.db.begin()
    
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        emp_doc = frappe.get_doc("Employee", employee)
        
        # Dictionary to store updates
        updates = {}
        
        # Define field configurations
        field_config = {
            'custom_tshirt_size': {'type': 'data', 'reentry': False},
            'custom_raincoat_size': {'type': 'data', 'reentry': False},
            'custom_trouser_size': {'type': 'data', 'reentry': False},
            'custom_shoe_size': {'type': 'data', 'reentry': False},
            'custom_helmet_size': {'type': 'data', 'reentry': False}
        }

        # Process each field
        for field_name, config in field_config.items():
            field_value = locals().get(field_name)
            if field_value is None:
                continue

            current_value = getattr(emp_doc, field_name)
            
            # Check if update is allowed
            can_update = (
                is_reentry_allowed and config['reentry']  # Re-entry is allowed for this field
                or not current_value  # Field is empty
                or (not config['reentry'] and not current_value)  # No re-entry and field is empty
            )

            if not can_update:
                continue

            updates[field_name] = field_value

        # If there are updates, apply them
        if updates:
            for field, value in updates.items():
                emp_doc.db_set(field, value, update_modified=True)
            
            frappe.db.commit()
            
            frappe.local.response['http_status_code'] = 200
            return {
                "success": True,
                "status": "success",
                "message": "Uniform sizes updated successfully",
                "code": "UNIFORM_SIZES_UPDATED",
                "data": updates,
                "http_status_code": 200
            }
        else:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "No fields to update or updates not allowed",
                "code": "NO_UPDATES_NEEDED",
                "http_status_code": 400
            }
            
    except Exception as e:
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error updating uniform sizes")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_employee_bank_details(
    bank_name: str = None,
    custom_ifsc_no: str = None,
    custom_beneficiary_name: str = None,
    bank_ac_no: str = None,
    custom_helmet_size: str = None,
    is_reentry_allowed: bool = False
) -> Dict[str, Any]:
    """
    Update employee bank details with conditional re-entry
    Required header: Authorization Bearer token
    """
    frappe.db.begin()
    
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        emp_doc = frappe.get_doc("Employee", employee)
        
        # Dictionary to store updates
        updates = {}
        
        # Define field configurations
        field_config = {
            'bank_name': {'type': 'data', 'reentry': False},
            'custom_ifsc_no': {'type': 'data', 'reentry': False},
            'custom_beneficiary_name': {'type': 'data', 'reentry': False},
            'bank_ac_no': {'type': 'data', 'reentry': False},
            'custom_helmet_size': {'type': 'data', 'reentry': False}
        }

        # Process each field
        for field_name, config in field_config.items():
            field_value = locals().get(field_name)
            if field_value is None:
                continue

            current_value = getattr(emp_doc, field_name)
            
            # Check if update is allowed
            can_update = (
                is_reentry_allowed and config['reentry']  # Re-entry is allowed for this field
                or not current_value  # Field is empty
                or (not config['reentry'] and not current_value)  # No re-entry and field is empty
            )

            if not can_update:
                continue

            updates[field_name] = field_value

        # If there are updates, apply them
        if updates:
            for field, value in updates.items():
                emp_doc.db_set(field, value, update_modified=True)
            
            frappe.db.commit()
            
            frappe.local.response['http_status_code'] = 200
            return {
                "success": True,
                "status": "success",
                "message": "Bank details updated successfully",
                "code": "BANK_DETAILS_UPDATED",
                "data": updates,
                "http_status_code": 200
            }
        else:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "No fields to update or updates not allowed",
                "code": "NO_UPDATES_NEEDED",
                "http_status_code": 400
            }
            
    except Exception as e:
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error updating bank details")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_employee_profile_image(image: str = None) -> Dict[str, Any]:
    """
    Update employee profile image
    Required header: Authorization Bearer token
    Args:
        image: Base64 encoded image string
    """
    frappe.db.begin()
    
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result
        
        if not image:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Profile image is required",
                "code": "IMAGE_REQUIRED",
                "http_status_code": 400
            }
        
        employee = result["employee"]
        emp_doc = frappe.get_doc("Employee", employee)
        
        try:
            image_result = handle_base64_image(image, prefix="profile_image")
            emp_doc.db_set('image', image_result['file_url'], update_modified=True)
            
            frappe.db.commit()
            
            frappe.local.response['http_status_code'] = 200
            return {
                "success": True,
                "status": "success",
                "message": "Profile image updated successfully",
                "code": "PROFILE_IMAGE_UPDATED",
                "data": {"image_url": image_result['file_url']},
                "http_status_code": 200
            }
        except Exception as e:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": f"Failed to process image: {str(e)}",
                "code": "IMAGE_PROCESSING_FAILED",
                "http_status_code": 400
            }
            
    except Exception as e:
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error updating profile image")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_employee_details() -> Dict[str, Any]:
    """
    Get all employee details including documents, vehicle details, uniform sizes, and bank details
    Required header: Authorization Bearer token
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        emp_doc = frappe.get_doc("Employee", employee)
        
        # Convert date fields to dd-mm-yyyy format
        date_fields = [
            'custom_vehicle_insurance_expiry',
            'custom_pollution_certificate_expiry'
        ]

        reporting_manager = {}
        if emp_doc.reports_to:
            reporting_manager = frappe.db.get_value(
                "Employee",
                emp_doc.reports_to,
                ["employee_name", "cell_number"],
                as_dict=True
            )
        
        employee_data = {
            "basic_details": {
                "employee_name": emp_doc.employee_name ,
                "cell_number": emp_doc.cell_number,
                "image": emp_doc.image,
                "reporting_manager_name" : reporting_manager.employee_name if reporting_manager else "N/A",
                "reporting_manager_cell_number" : reporting_manager.cell_number if reporting_manager else "N/A"
            }
        }

        
        # Document details
        document_fields = [
            'custom_aadhaar_card_number',
            'custom_pan',
            'custom_aadhaar_front',
            'custom_aadhaar_back',
            'custom_pan_image'
        ]
        employee_data['documents'] = {
            field: getattr(emp_doc, field) for field in document_fields
        }
        
        # Vehicle details
        vehicle_fields = [
            'custom_vehicle_type',
            'custom_vehicle_registration_number',
            'custom_driving_license_number',
            'custom_driving_license_photo',
            'custom_vehicle_insurance_number',
            'custom_vehicle_insurance_expiry',
            'custom_vehicle_insurance_photo',
            'custom_pollution_certificate_number',
            'custom_pollution_certificate_expiry',
            'custom_pollution_certificate_photo'
        ]
        employee_data['vehicle_details'] = {
            field: getattr(emp_doc, field) for field in vehicle_fields
        }
        
        # Convert date fields
        for field in date_fields:
            if employee_data['vehicle_details'].get(field):
                date_obj = datetime.datetime.strptime(
                    str(employee_data['vehicle_details'][field]), 
                    '%Y-%m-%d'
                )
                employee_data['vehicle_details'][field] = date_obj.strftime('%d-%m-%Y')
        
        # Uniform sizes
        uniform_fields = [
            'custom_tshirt_size',
            'custom_raincoat_size',
            'custom_trouser_size',
            'custom_shoe_size',
            'custom_helmet_size'
        ]
        employee_data['uniform_sizes'] = {
            field: getattr(emp_doc, field) for field in uniform_fields
        }
        
        # Bank details
        bank_fields = [
            'bank_name',
            'custom_ifsc_no',
            'custom_beneficiary_name',
            'bank_ac_no'
        ]
        employee_data['bank_details'] = {
            field: getattr(emp_doc, field) for field in bank_fields
        }
        
        # Profile image
        employee_data['profile_image'] = emp_doc.image
        
        # Basic details
        employee_data['basic_details'] = {
            'employee_name': emp_doc.employee_name,
            'employee_id': emp_doc.name
        }
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Employee details retrieved successfully",
            "code": "DETAILS_RETRIEVED",
            "data": employee_data,
            "http_status_code": 200
        }
        
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving employee details")

