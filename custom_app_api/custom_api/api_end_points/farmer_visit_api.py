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

# @frappe.whitelist(allow_guest=True, methods=["POST"])
# def create_farmer_visit(
#     farmer_name: str = None,
#     farmer_create_detail: Dict = None,
#     visit_tracker_detail: Dict[str, Any] = None
# ) -> Dict[str, Any]:
#     """
#     Creates a farmer visit record with optional farmer creation
#     Required header: Authorization Bearer token
#     """
#     # Start transaction
#     frappe.db.begin()
    
#     try:
#         # Verify authorization
#         is_valid, result = verify_dp_token(frappe.request.headers)
#         if not is_valid:
#             frappe.db.rollback()
#             frappe.local.response['http_status_code'] = 401
#             return result
        
#         employee = result["employee"]
        
#         # Validate input parameters
#         if not farmer_name and not farmer_create_detail:
#             frappe.db.rollback()
#             frappe.local.response['http_status_code'] = 400
#             return {
#                 "success": False,
#                 "status": "error",
#                 "message": "Either farmer_name or farmer_create_detail must be provided",
#                 "code": "INVALID_INPUT",
#                 "http_status_code": 400
#             }

#         try:
#             # Create new farmer if details provided
#             if farmer_create_detail:
#                 # Check for duplicate mobile number
#                 if 'contact_number' in farmer_create_detail:
#                     existing_farmer = frappe.get_all(
#                         "Farmer Details",
#                         filters={"contact_number": farmer_create_detail['contact_number']},
#                         fields=["name", "first_name", "last_name"]
#                     )
                    
#                     if existing_farmer:
#                         frappe.db.rollback()
#                         farmer_info = existing_farmer[0]
#                         frappe.local.response['http_status_code'] = 400
#                         return {
#                             "success": False,
#                             "status": "error",
#                             "message": f"Mobile number {farmer_create_detail['contact_number']} is already registered "
#                                      f"with farmer {farmer_info.first_name} {farmer_info.last_name} ({farmer_info.name})",
#                             "code": "DUPLICATE_MOBILE",
#                             "http_status_code": 400
#                         }

#                 farmer = frappe.get_doc({
#                     "doctype": "Farmer Details",
#                     "registered_by": employee,
#                     **farmer_create_detail
#                 })
#                 farmer.insert()
#                 farmer_name = farmer.name

#             # Handle base64 image
#             if visit_tracker_detail and "visit_image" in visit_tracker_detail:
#                 try:
#                     image_result = handle_base64_image(
#                         visit_tracker_detail["visit_image"],
#                         prefix="visit"
#                     )
#                     visit_tracker_detail["visit_image"] = image_result["file_url"]
#                 except Exception as e:
#                     frappe.db.rollback()
#                     frappe.local.response['http_status_code'] = 400
#                     return {
#                         "success": False,
#                         "status": "error",
#                         "message": f"Failed to process image: {str(e)}",
#                         "code": "IMAGE_PROCESSING_FAILED",
#                         "http_status_code": 400
#                     }

#             # Create visit tracker record
#             visit = frappe.get_doc({
#                 "doctype": "Visit Tracker",
#                 "farmer": farmer_name,
#                 "visited_by": employee,
#                 **visit_tracker_detail
#             })
#             visit.insert()
#             visit.submit()  # Submit the document

#             # If everything is successful, commit the transaction
#             frappe.db.commit()

#             frappe.local.response['http_status_code'] = 201
#             return {
#                 "success": True,
#                 "status": "success",
#                 "message": "Visit record created successfully",
#                 "code": "VISIT_CREATED",
#                 "data": {
#                     "visit_id": visit.name,
#                     "farmer_id": farmer_name
#                 },
#                 "http_status_code": 201
#             }

#         except Exception as e:
#             frappe.db.rollback()
#             frappe.local.response['http_status_code'] = 400
#             return {
#                 "success": False,
#                 "status": "error",
#                 "message": str(e),
#                 "code": "CREATION_FAILED",
#                 "http_status_code": 400
#             }

#     except Exception as e:
#         frappe.db.rollback()
#         frappe.local.response['http_status_code'] = 500
#         return handle_error_response(e, "Error creating farmer visit")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def create_farmer_visit(
    farmer_create_detail: Dict,
    visit_tracker_detail: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Creates a farmer and it's visit record
    Required header: Authorization Bearer token
    """

    # Start transaction
    frappe.db.begin()

    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result

        employee = result["employee"]

        #check dublicate mobile number
        if 'contact_number' in farmer_create_detail:
            existing_farmer = frappe.get_all(
                "Farmer Details",
                filters={"contact_number": farmer_create_detail['contact_number']},
                fields=["name", "first_name", "last_name"]
            )

            if existing_farmer:
                frappe.db.rollback()
                farmer_info = existing_farmer[0]
                frappe.local.response['http_status_code'] = 400
                return {
                    "success": False,
                    "status": "error",
                    "message": f"Mobile number {farmer_create_detail['contact_number']} is already registered "
                             f"with farmer {farmer_info.first_name} {farmer_info.last_name} ({farmer_info.name})",
                    "code": "DUPLICATE_MOBILE",
                    "http_status_code": 400
                }

        farmer = frappe.get_doc({
            "doctype": "Farmer Details",
            "registered_by": employee,
            "assigned_sales_person": employee,
            **farmer_create_detail
        })
        farmer.insert()

        farmer_name = farmer.name

        #handle base64 image
        if visit_tracker_detail and "visit_image" in visit_tracker_detail:
            try:
                image_result = handle_base64_image(
                    visit_tracker_detail["visit_image"],
                    prefix="visit"
                )
                visit_tracker_detail["visit_image"] = image_result["file_url"]
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
        
        #create visit tracker record
        visit = frappe.get_doc({
            "doctype": "Visit Tracker",
            "farmer": farmer_name,
            "visited_by": employee,
            **visit_tracker_detail
        })
        visit.insert()
        visit.submit()

        #commit transaction
        frappe.db.commit()

        frappe.local.response['http_status_code'] = 201

        return {
            "success": True,
            "status": "success",
            "message": "Farmer and visit record created successfully",
            "code": "FARMER_VISIT_CREATED",
            "data": {
                "farmer_id": farmer_name,
                "visit_id": visit.name
            },
            "http_status_code": 201
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error creating farmer and visit record")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def create_farmer_revisit(
    farmer_id: str,
    previous_visit_id: str,
    farmer_prospect_type: str,
    visit_tracker_detail: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    It requires farmer_id, previous_visit_id, farmer_prospect_type and visit_tracker_detail
    It will validate the farmer_id and previous_visit_id and create a new visit record
    And it will also make sure there are no revisit entry made for the given previous_visit_id
    Required header: Authorization Bearer token
    """

    # Start transaction
    frappe.db.begin()

    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]

        #farmer details
        farmer = frappe.get_doc("Farmer Details", farmer_id)

        if not farmer:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "Farmer not found",
                "code": "FARMER_NOT_FOUND",
                "http_status_code": 404
            }

        #previous visit details
        previous_visit = frappe.get_doc("Visit Tracker", previous_visit_id)

        if not previous_visit:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "Previous visit not found",
                "code": "PREVIOUS_VISIT_NOT_FOUND",
                "http_status_code": 404
            }

        # Check if the previous visit has already been followed up
        if previous_visit.follow_up_visit:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "This visit already has a follow-up visit",
                "code": "FOLLOW_UP_EXISTS",
                "http_status_code": 400
            }

        #create new revisit record

        # Handle base64 image
        if visit_tracker_detail and "visit_image" in visit_tracker_detail:
            try:
                image_result = handle_base64_image(
                    visit_tracker_detail["visit_image"],
                    prefix="visit"
                )
                visit_tracker_detail["visit_image"] = image_result["file_url"]
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

        # Create visit tracker record
        visit = frappe.get_doc({
            "doctype": "Visit Tracker",
            "farmer": farmer_id,
            "visited_by": employee,
            "is_revisit": 1,
            "last_visit": previous_visit_id,
            **visit_tracker_detail
        })
        visit.insert()
        visit.submit()  # Submit the document

        # Update the previous visit's follow_up_visit field using db_set
        previous_visit.db_set('follow_up_visit', visit.name, update_modified=False)

        # Update the farmer's prospect type
        farmer.db_set('prospect_type', farmer_prospect_type, update_modified=True)

        frappe.db.commit()

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
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error creating farmer revisit")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_assigned_farmers() -> Dict[str, Any]:
    """
    Returns list of farmers registered by the logged-in employee
    Required header: Authorization Bearer token
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get farmers registered by the employee
        farmers = frappe.get_all(
            "Farmer Details",
            filters={"assigned_sales_person": employee},
            fields=[
                "name",
                "first_name",
                "last_name",
                "contact_number",
                "address",
                "prospect_type",
                "bmc",
                "age",
                "family_background",
                "financial_status",
                "educational_qualification"
            ]
        )
        
        if not farmers:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "No farmers found for this employee",
                "code": "NO_FARMERS_FOUND",
                "http_status_code": 404
            }

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Farmers list retrieved successfully",
            "code": "FARMERS_RETRIEVED",
            "data": farmers,
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving farmers list")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_assigned_farmers_list() -> Dict[str, Any]:
    """
    Returns paginated list of farmers assigned to the logged-in employee as sales person
    Required header: Authorization Bearer token
    Query params:
        page_number: int (default=1)
        page_size: int (default=10)
        prospect_type: str (optional)
        first_name: str (optional)
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get query parameters
        page_number = int(frappe.request.args.get('page_number', 1))
        page_size = int(frappe.request.args.get('page_size', 10))
        prospect_type = frappe.request.args.get('prospect_type')
        first_name = frappe.request.args.get('first_name')
        
        # Calculate offset
        offset = (page_number - 1) * page_size
        
        # Build filters
        filters = {"assigned_sales_person": employee}
        if prospect_type:
            filters["prospect_type"] = prospect_type
        if first_name:
            filters["first_name"] = ("like", f"%{first_name}%")
        
        # Get total count for pagination
        total_farmers = frappe.db.count("Farmer Details", filters=filters)
        
        # Get farmers with pagination
        farmers = frappe.get_all(
            "Farmer Details",
            filters=filters,
            fields=["name", "first_name", "last_name", "age", "prospect_type"],
            start=offset,
            page_length=page_size
        )
        
        # Get visit statistics for each farmer
        for farmer in farmers:
            visits = frappe.get_all(
                "Visit Tracker",
                filters={"farmer": farmer.name, "docstatus": 1},
                fields=["name", "creation"],
                order_by="creation desc"
            )
            
            farmer["total_visits"] = len(visits)
            farmer["last_visit_date"] = visits[0].creation if visits else None
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Farmers list retrieved successfully",
            "code": "FARMERS_RETRIEVED",
            "data": {
                "farmers": farmers,
                "pagination": {
                    "farmer_list": total_farmers,
                    "page_size": page_size,
                    "current_page": page_number,
                    "total_pages": (total_farmers + page_size - 1) // page_size
                }
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving assigned farmers list")

@frappe.whitelist(allow_guest=True, methods=["PUT"])
def update_farmer_details(farmer_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates specific fields of a farmer's details
    Required header: Authorization Bearer token
    Args:
        farmer_id: ID of the farmer to update
        update_data: Dictionary containing fields to update
    Allowed fields for update:
        - first_name
        - last_name
        - age
        - contact_number
        - prospect_type
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Validate farmer exists and belongs to the employee
        farmer = frappe.get_doc("Farmer Details", farmer_id)
        if farmer.assigned_sales_person != employee:
            frappe.local.response['http_status_code'] = 403
            return {
                "success": False,
                "status": "error",
                "message": "You don't have permission to update this farmer's details",
                "code": "PERMISSION_DENIED",
                "http_status_code": 403
            }
        
        # List of allowed fields for update
        allowed_fields = [
            "first_name",
            "last_name",
            "age",
            "contact_number",
            "prospect_type"
        ]
        
        # Validate update data
        update_fields = {}
        for field in allowed_fields:
            if field in update_data:
                # Special validation for contact number
                if field == "contact_number":
                    # Skip if number hasn't changed
                    if update_data[field] == farmer.get(field):
                        continue
                        
                    # Check for duplicate contact number
                    existing = frappe.get_all(
                        "Farmer Details",
                        filters={
                            "contact_number": update_data[field],
                            "name": ("!=", farmer_id)
                        },
                        fields=["name", "first_name", "last_name"]
                    )
                    if existing:
                        farmer_info = existing[0]
                        frappe.local.response['http_status_code'] = 400
                        return {
                            "success": False,
                            "status": "error",
                            "message": f"Mobile number {update_data[field]} is already registered "
                                     f"with farmer {farmer_info.first_name} {farmer_info.last_name} ({farmer_info.name})",
                            "code": "DUPLICATE_MOBILE",
                            "http_status_code": 400
                        }
                
                # Special validation for age
                if field == "age" and not isinstance(update_data[field], int):
                    frappe.local.response['http_status_code'] = 400
                    return {
                        "success": False,
                        "status": "error",
                        "message": "Age must be a number",
                        "code": "INVALID_AGE",
                        "http_status_code": 400
                    }
                
                update_fields[field] = update_data[field]
        
        if not update_fields:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "No valid fields to update",
                "code": "NO_UPDATES",
                "http_status_code": 400
            }
        
        # Update farmer details
        farmer.update(update_fields)
        farmer.save()
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Farmer details updated successfully",
            "code": "FARMER_UPDATED",
            "data": {
                "farmer_id": farmer_id,
                "updated_fields": list(update_fields.keys())
            },
            "http_status_code": 200
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response['http_status_code'] = 404
        return {
            "success": False,
            "status": "error",
            "message": "Farmer not found",
            "code": "FARMER_NOT_FOUND",
            "http_status_code": 404
        }
    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error updating farmer details")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_visits_list() -> Dict[str, Any]:
    """
    Returns paginated list of visits made by the logged-in employee
    Required header: Authorization Bearer token
    Query params:
        page_number: int (default=1)
        page_size: int (default=10)
        visit_type: str (optional) - "Phone Call" or "Physical Visit"
        village: str (optional) - Village ID
        requested_revisit: int (optional) - 0 or 1
        is_revisit: int (optional) - 0 or 1
        farmer: str (optional) - Farmer ID
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get query parameters
        page_number = int(frappe.request.args.get('page_number', 1))
        page_size = int(frappe.request.args.get('page_size', 10))
        
        # Get filter parameters
        visit_type = frappe.request.args.get('visit_type')
        village = frappe.request.args.get('village')
        requested_revisit = frappe.request.args.get('requested_revisit')
        is_revisit = frappe.request.args.get('is_revisit')
        farmer = frappe.request.args.get('farmer')
        
        # Calculate offset
        offset = (page_number - 1) * page_size
        
        # Build filters
        filters = {
            "visited_by": employee,
            "docstatus": 1  # Only get submitted documents
        }
        
        # Add optional filters if provided
        if visit_type:
            filters["visit_type"] = visit_type
        if village:
            filters["village"] = village
        if requested_revisit is not None:
            filters["requested_revisit"] = int(requested_revisit)
        if is_revisit is not None:
            filters["is_revisit"] = int(is_revisit)
        if farmer:
            filters["farmer"] = farmer
        
        # Get total count for pagination
        total_visits = frappe.db.count("Visit Tracker", filters=filters)
        
        # Get visits with pagination
        visits = frappe.get_all(
            "Visit Tracker",
            filters=filters,
            fields=[
                "name",
                "farmer",
                "visit_date",
                "visit_type",
                "village",
                "requested_revisit",
                "is_revisit",
                "visit_reason",
                "comments",
                "follow_up_visit",
                #"visit_image"
            ],
            order_by="visit_date desc",
            start=offset,
            page_length=page_size
        )
        
        # Get additional details for each visit
        for visit in visits:
            # Get farmer details
            farmer_doc = frappe.get_doc("Farmer Details", visit.farmer)
            visit["farmer_name"] = f"{farmer_doc.first_name} {farmer_doc.last_name}"
            
            # Get village name if village exists
            if visit.village:
                village_doc = frappe.get_doc("Village", visit.village)
                visit["village_name"] = village_doc.village_name
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Visits list retrieved successfully",
            "code": "VISITS_RETRIEVED",
            "data": {
                "visits": visits,
                "pagination": {
                    "total_records": total_visits,
                    "page_size": page_size,
                    "current_page": page_number,
                    "total_pages": (total_visits + page_size - 1) // page_size
                }
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving visits list")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_pending_revisits() -> Dict[str, Any]:
    """
    Returns list of pending revisits for the logged-in employee
    Required header: Authorization Bearer token
    Query params:
        start_date: str (optional) - format: YYYY-MM-DD (default: start of current month)
        end_date: str (optional) - format: YYYY-MM-DD (default: end of current month)
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get current date
        today = frappe.utils.today()
        
        # Get start and end dates from query params or use defaults
        try:
            # Default: Start of current month
            start_date = frappe.request.args.get('start_date') or frappe.utils.data.get_first_day(today)
            # Default: End of current month
            end_date = frappe.request.args.get('end_date') or frappe.utils.data.get_last_day(today)
        except Exception as e:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD",
                "code": "INVALID_DATE_FORMAT",
                "http_status_code": 400
            }
        
        # Get pending revisits
        visits = frappe.get_all(
            "Visit Tracker",
            filters={
                "visited_by": employee,
                "docstatus": 1,  # Only submitted documents
                "requested_revisit": 1,  # Only visits that requested revisit
                "follow_up_visit": ("is", "not set"),  # No follow-up visit created yet
                "revisit_on": ["between", [start_date, end_date]]
            },
            fields=[
                "name",
                "farmer",
                "visit_date",
                "visit_type",
                "village",
                "revisit_on",
                "visit_reason",
                "comments"
            ],
            order_by="revisit_on asc"  # Order by revisit date
        )
        
        # Get additional details for each visit
        for visit in visits:
            # Get farmer details
            farmer_doc = frappe.get_doc("Farmer Details", visit.farmer)
            visit["farmer_name"] = f"{farmer_doc.first_name} {farmer_doc.last_name}"
            visit["farmer_contact"] = farmer_doc.contact_number
            visit["prospect_type"] = farmer_doc.prospect_type
            
            # Get village name if village exists
            if visit.village:
                village_doc = frappe.get_doc("Village", visit.village)
                visit["village_name"] = village_doc.village_name
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Pending revisits retrieved successfully",
            "code": "REVISITS_RETRIEVED",
            "data": {
                "visits": visits,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date
                }
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving pending revisits")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_prospect_statistics() -> Dict[str, Any]:
    """
    Returns prospect statistics for farmers assigned to the logged-in employee
    Required header: Authorization Bearer token
    Query params:
        start_date: str - format: YYYY-MM-DD
        end_date: str - format: YYYY-MM-DD
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get date filters from query params
        start_date = frappe.request.args.get('start_date')
        end_date = frappe.request.args.get('end_date')
        
        if not start_date or not end_date:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Both start_date and end_date are required",
                "code": "MISSING_DATE_FILTERS",
                "http_status_code": 400
            }
        
        try:
            # Validate date format
            frappe.utils.getdate(start_date)
            frappe.utils.getdate(end_date)
        except Exception:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD",
                "code": "INVALID_DATE_FORMAT",
                "http_status_code": 400
            }
        
        # Base filters
        base_filters = {
            "assigned_sales_person": employee,
            "creation": ["between", [start_date, end_date]]
        }
        print(base_filters)
        
        # Get total farmers count
        total_farmers = frappe.db.count("Farmer Details", filters=base_filters)
        print(total_farmers)
        # Get prospect type counts
        prospect_types = ["Hot", "Warm", "Cold", "Lost", "Converted"]
        prospect_counts = {}
        
        for prospect_type in prospect_types:
            filters = base_filters.copy()
            filters["prospect_type"] = prospect_type
            count = frappe.db.count("Farmer Details", filters=filters)
            prospect_counts[f"{prospect_type.lower()}_prospect"] = count
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Prospect statistics retrieved successfully",
            "code": "STATISTICS_RETRIEVED",
            "data": {
                "total_farmers": total_farmers,
                **prospect_counts,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date
                }
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving prospect statistics")

