import frappe
from frappe import _
from typing import Dict, Any
import base64
import os
from .attendance_api import verify_dp_token, handle_error_response

def handle_base64_image(base64_string: str, prefix: str = "file", is_private: int = 1) -> Dict[str, str]:
    """
    Handle base64 image upload
    Args:
        base64_string: Base64 encoded image string
        prefix: Prefix for the file name
        is_private: Whether the file should be private (1) or public (0)
    Returns:
        Dict containing file_url and other file details
    """
    try:
        # Remove the data URL prefix if present
        if "base64," in base64_string:
            base64_string = base64_string.split("base64,")[1]

        # Decode base64 string
        file_content = base64.b64decode(base64_string)

        # Generate a unique filename
        filename = f"{prefix}_{frappe.generate_hash()[:10]}.png"

        # Create a new file doc
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "is_private": is_private,
            "content": file_content,
            "decode": True
        })
        
        file_doc.insert()

        return {
            "name": file_doc.name,
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url
        }

    except Exception as e:
        frappe.throw(f"Error processing image: {str(e)}")

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

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_assigned_villages() -> Dict[str, Any]:
    """
    Returns list of villages assigned to the logged-in employee
    Required header: Authorization Bearer token
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get village mapping for the employee
        village_mapping = frappe.get_all(
            "Village BDE Mapping",
            filters={"employee": employee},
            fields=["name"]
        )
        
        if not village_mapping:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "No villages assigned to this employee",
                "code": "NO_VILLAGES_ASSIGNED",
                "http_status_code": 404
            }
            
        # Get village details from the mapping
        villages = frappe.get_all(
            "Village Map",
            filters={"parent": village_mapping[0].name},
            fields=["village"],
            as_list=False
        )
        
        # Get complete village information
        village_details = []
        for village in villages:
            village_doc = frappe.get_doc("Village", village.village)
            village_details.append({
                "name": village_doc.name,
                "village_name": village_doc.village_name,
                "state": village_doc.state,
                "pincode": village_doc.pincode,
                "latitude": village_doc.latitude,
                "longitude": village_doc.longitude,
                "nearest_towncity": village_doc.nearest_towncity
            })

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Villages retrieved successfully",
            "code": "VILLAGES_RETRIEVED",
            "data": village_details,
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving assigned villages")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_bmc_list() -> Dict[str, Any]:
    """
    Returns list of all BMCs
    Required header: Authorization Bearer token
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        # Get all BMCs
        bmc_list = frappe.get_all(
            "BMC",
            fields=["name", "bmc_name", "state", "location"]
        )
        
        if not bmc_list:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "No BMCs found",
                "code": "NO_BMCS_FOUND",
                "http_status_code": 404
            }

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "BMC list retrieved successfully",
            "code": "BMC_LIST_RETRIEVED",
            "data": bmc_list,
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving BMC list")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_farmer_visit(
    farmer_name: str = None,
    farmer_create_detail: Dict = None,
    visit_tracker_detail: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Creates a farmer visit record with optional farmer creation
    Required header: Authorization Bearer token
    """
    try:
        # Log incoming request data
        frappe.logger().debug(f"Create Farmer Visit - Input Data: farmer_name={farmer_name}, "
                            f"farmer_create_detail={farmer_create_detail}, "
                            f"visit_tracker_detail={visit_tracker_detail}")

        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.logger().error(f"Authorization failed: {result}")
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        frappe.logger().debug(f"Authorized employee: {employee}")

        # Validate input parameters
        if not farmer_name and not farmer_create_detail:
            frappe.logger().error("Neither farmer_name nor farmer_create_detail provided")
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Either farmer_name or farmer_create_detail must be provided",
                "code": "INVALID_INPUT",
                "http_status_code": 400
            }

        # Create new farmer if details provided
        if farmer_create_detail:
            try:
                frappe.logger().debug(f"Creating new farmer with details: {farmer_create_detail}")
                farmer = frappe.get_doc({
                    "doctype": "Farmer Details",
                    "registered_by": employee,
                    **farmer_create_detail
                })
                farmer.insert()
                farmer_name = farmer.name
                frappe.logger().info(f"New farmer created: {farmer_name}")
            except Exception as e:
                frappe.logger().error(f"Farmer creation failed: {str(e)}\nDetails: {farmer_create_detail}")
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": f"Failed to create farmer: {str(e)}",
                    "code": "FARMER_CREATION_FAILED",
                    "http_status_code": 400
                }

        # Handle base64 image
        if visit_tracker_detail and "visit_image" in visit_tracker_detail:
            try:
                frappe.logger().debug("Processing visit image")
                image_result = handle_base64_image(
                    visit_tracker_detail.pop("visit_image"),
                    prefix="visit",
                    is_private=0
                )
                visit_tracker_detail["visit_image"] = image_result["file_url"]
                frappe.logger().debug(f"Image processed successfully: {image_result['file_url']}")
            except Exception as e:
                frappe.logger().error(f"Image processing failed: {str(e)}")
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": f"Failed to process image: {str(e)}",
                    "code": "IMAGE_PROCESSING_FAILED",
                    "http_status_code": 400
                }

        # Create visit tracker record
        try:
            frappe.logger().debug(f"Creating visit tracker with details: {visit_tracker_detail}")
            visit = frappe.get_doc({
                "doctype": "Visit Tracker",
                "farmer": farmer_name,
                "visited_by": employee,
                **visit_tracker_detail
            })
            visit.insert()
            visit.submit()  # Since it's a submittable document
            frappe.logger().info(f"Visit record created successfully: {visit.name}")

            frappe.local.response['http_status_code'] = 201
            return {
                "success": True,
                "status": "success",
                "message": "Visit record created successfully",
                "code": "VISIT_CREATED",
                "data": {
                    "visit_id": visit.name,
                    "farmer_id": farmer_name
                },
                "http_status_code": 201
            }

        except Exception as e:
            frappe.logger().error(f"Visit creation failed: {str(e)}\nDetails: {visit_tracker_detail}")
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": f"Failed to create visit: {str(e)}",
                "code": "VISIT_CREATION_FAILED",
                "http_status_code": 400
            }

    except Exception as e:
        frappe.logger().error(f"Unexpected error in create_farmer_visit: {str(e)}")
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error creating farmer visit")

