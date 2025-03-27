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
    Dynamically returns all select field options for Farmer Detail and Visit Tracker
    Required header: Authorization Bearer token
    """
    try:
        # Get the authorization header
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result

        doctypes = {
            "farmer_details": "Farmer Detail",
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
def get_bmc_list() -> Dict[str, Any]:
    """
    Returns list of BMCs associated with the villages in clusters mapped to the logged-in employee
    or BMCs in specified mandals
    Required header: Authorization Bearer token
    Query params:
        mandals: str (optional) - Comma separated list of mandal names
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        # Check for mandals in query params
        mandal_param = frappe.request.args.get('mandals')
        if mandal_param:
            # Split and clean mandal names
            mandals = [m.strip() for m in mandal_param.split(',') if m.strip()]
        else:
            employee = result["employee"]
            
            # Get the Cluster BDE Mapping document for this employee
            cluster_mapping_doc = frappe.get_all(
                "Cluster BDE Mapping",
                filters={"employee": employee},
                fields=["name"],
                limit_page_length=None
            )
            
            if not cluster_mapping_doc:
                frappe.local.response['http_status_code'] = 404
                return {
                    "success": False,
                    "status": "error",
                    "message": "No clusters mapped to this employee",
                    "code": "NO_CLUSTERS_MAPPED",
                    "http_status_code": 404
                }
            
            # Get all clusters from the Cluster Mapping child table
            clusters = frappe.get_all(
                "Cluster Mapping",
                filters={"parent": cluster_mapping_doc[0].name},
                fields=["cluster"],
                limit_page_length=None
            )
            
            if not clusters:
                frappe.local.response['http_status_code'] = 404
                return {
                    "success": False,
                    "status": "error",
                    "message": "No clusters found in mapping",
                    "code": "NO_CLUSTERS_FOUND",
                    "http_status_code": 404
                }
            
            # Get all villages from the mapped clusters
            villages = []
            for cluster in clusters:
                cluster_villages = frappe.get_all(
                    "Village Map",
                    filters={"parent": cluster.cluster},
                    fields=["village"],
                    limit_page_length=None
                )
                villages.extend([v.village for v in cluster_villages])
            
            if not villages:
                frappe.local.response['http_status_code'] = 404
                return {
                    "success": False,
                    "status": "error",
                    "message": "No villages found in mapped clusters",
                    "code": "NO_VILLAGES_FOUND",
                    "http_status_code": 404
                }
            
            # Get mandals for all villages
            mandals = list(set([
                frappe.get_value("Village", v, "mandal") 
                for v in villages 
                if frappe.get_value("Village", v, "mandal")
            ]))
            
            if not mandals:
                frappe.local.response['http_status_code'] = 404
                return {
                    "success": False,
                    "status": "error",
                    "message": "No mandals found for the mapped villages",
                    "code": "NO_MANDALS_FOUND",
                    "http_status_code": 404
                }

        # Get BMCs that have any of the specified mandals in their mandal_list
        bmc_mandals = frappe.get_all(
            "Mandal Map",
            filters={"mandal": ["in", mandals]},
            fields=["parent as bmc", "mandal"],
            limit_page_length=None
        )
        
        if not bmc_mandals:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "No BMCs found in the specified mandals",
                "code": "NO_BMCS_FOUND",
                "http_status_code": 404
            }

        # Group mandals by BMC
        bmc_dict = {}
        for entry in bmc_mandals:
            if entry.bmc not in bmc_dict:
                bmc_doc = frappe.get_doc("BMC", entry.bmc)
                bmc_dict[entry.bmc] = {
                    "name": entry.bmc,
                    "bmc_name": bmc_doc.bmc_name,
                    "state": bmc_doc.state,
                    "mandals": []
                }
            bmc_dict[entry.bmc]["mandals"].append(entry.mandal)

        bmc_list = list(bmc_dict.values())

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
        
        # Get the Cluster BDE Mapping document for this employee
        cluster_mapping_doc = frappe.get_all(
            "Cluster BDE Mapping",
            filters={"employee": employee},
            fields=["name"],
            limit_page_length=None
        )
        
        if not cluster_mapping_doc:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "No clusters mapped to this employee",
                "code": "NO_CLUSTERS_MAPPED",
                "http_status_code": 404
            }
        
        # Get all clusters from the Cluster Mapping child table
        clusters = frappe.get_all(
            "Cluster Mapping",
            filters={"parent": cluster_mapping_doc[0].name},
            fields=["cluster"],
            limit_page_length=None
        )
        
        if not clusters:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "No clusters found in mapping",
                "code": "NO_CLUSTERS_FOUND",
                "http_status_code": 404
            }
        
        # Get all villages from the mapped clusters
        villages = []
        for cluster in clusters:
            cluster_villages = frappe.get_all(
                "Village Map",
                filters={"parent": cluster.cluster},
                fields=["village"],
                limit_page_length=None
            )
            villages.extend([v.village for v in cluster_villages])
        
        if not villages:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "No villages found in mapped clusters",
                "code": "NO_VILLAGES_FOUND",
                "http_status_code": 404
            }
        
        # Get complete village information
        village_details = []
        for village in villages:
            village_doc = frappe.get_doc("Village", village)
            village_details.append({
                "name": village_doc.name,
                "mandal": village_doc.mandal,
                "village_name": village_doc.village_name,
                "district": village_doc.district,
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

@frappe.whitelist(allow_guest=True, methods=["POST"])
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
        # Log incoming request data
        frappe.log_error(
            title="Create Farmer Visit - Request Data",
            message={
                "farmer_create_detail": farmer_create_detail,
                "visit_tracker_detail": visit_tracker_detail
            }
        )

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
                "Farmer Detail",
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
        
        #if annual_income is <1 Lakh then financial_status is Weak, 
        #if annual_income is 1-3 Lakh then financial_status is Average,
        #if annual_income is >3 Lakh then financial_status is Good
        if 'annual_income' in farmer_create_detail:
            if farmer_create_detail['annual_income'] == "<1 Lakh":
                farmer_create_detail['financial_status'] = "Weak"
            elif farmer_create_detail['annual_income'] == "1 - 3Lakh":
                farmer_create_detail['financial_status'] = "Average"
            elif farmer_create_detail['annual_income'] == ">3Lakh":
                farmer_create_detail['financial_status'] = "Good"

        # Log farmer creation attempt
        frappe.log_error(
            title="Create Farmer Visit - Creating Farmer",
            message={
                "employee": employee,
                "farmer_data": farmer_create_detail
            }
        )

        #create farmer record
        farmer = frappe.get_doc({
            "doctype": "Farmer Detail",
            "registered_by": employee,
            "assigned_sales_person": employee,
            **farmer_create_detail
        })

        farmer.insert()
        farmer_name = farmer.name

        # Log successful farmer creation
        frappe.log_error(
            title="Create Farmer Visit - Farmer Created",
            message={
                "farmer_id": farmer_name,
                "farmer_data": farmer.as_dict()
            }
        )

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
        
        # Log visit creation attempt
        frappe.log_error(
            title="Create Farmer Visit - Creating Visit",
            message={
                "farmer_id": farmer_name,
                "visit_data": visit_tracker_detail
            }
        )

        #create visit tracker record
        visit = frappe.get_doc({
            "doctype": "Visit Tracker",
            "farmer": farmer_name,
            "visited_by": employee,
            **visit_tracker_detail
        })
        visit.insert()
        visit.submit()

        # Log successful visit creation
        frappe.log_error(
            title="Create Farmer Visit - Visit Created",
            message={
                "visit_id": visit.name,
                "visit_data": visit.as_dict()
            }
        )

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
        frappe.log_error(
            title="Create Farmer Visit - Error",
            message={
                "error": str(e),
                "farmer_create_detail": farmer_create_detail,
                "visit_tracker_detail": visit_tracker_detail,
                "traceback": frappe.get_traceback()
            }
        )
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error creating farmer and visit record")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_farmer_revisit(
    farmer_id: str,
    farmer_prospect_type: str,
    previous_visit_id: str = None,
    visit_tracker_detail: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Creates a revisit record for a farmer
    Required header: Authorization Bearer token
    Args:
        farmer_id: ID of the farmer
        farmer_prospect_type: Updated prospect type for the farmer
        previous_visit_id: Optional ID of the previous visit
        visit_tracker_detail: Details of the visit
    """
    # Start transaction
    frappe.db.begin()

    try:
        # Log incoming request data
        frappe.log_error(
            title="Create Farmer Revisit - Request Data",
            message={
                "farmer_id": farmer_id,
                "farmer_prospect_type": farmer_prospect_type,
                "previous_visit_id": previous_visit_id,
                "visit_tracker_detail": visit_tracker_detail
            }
        )

        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]

        # Log farmer fetch attempt
        frappe.log_error(
            title="Create Farmer Revisit - Fetching Farmer",
            message={
                "farmer_id": farmer_id,
                "employee": employee
            }
        )

        # Farmer detail
        farmer = frappe.get_doc("Farmer Detail", farmer_id)

        if not farmer:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "Farmer not found",
                "code": "FARMER_NOT_FOUND",
                "http_status_code": 404
            }

        # Check previous visit only if provided
        if previous_visit_id:
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

        # Log visit creation attempt
        frappe.log_error(
            title="Create Farmer Revisit - Creating Visit",
            message={
                "farmer_id": farmer_id,
                "visit_data": visit_tracker_detail,
                "previous_visit_id": previous_visit_id
            }
        )

        # Create visit tracker record
        visit_data = {
            "doctype": "Visit Tracker",
            "farmer": farmer_id,
            "visited_by": employee,
            "is_revisit": 1
        }

        # Add last_visit only if previous_visit_id is provided
        if previous_visit_id:
            visit_data["last_visit"] = previous_visit_id

        if visit_tracker_detail:
            visit_data.update(visit_tracker_detail)

        visit = frappe.get_doc(visit_data)
        visit.insert()
        visit.submit()  # Submit the document

        # Update the previous visit's follow_up_visit field if previous_visit_id exists
        if previous_visit_id:
            previous_visit.db_set('follow_up_visit', visit.name, update_modified=False)

        # Update the farmer's prospect type
        farmer.db_set('prospect_type', farmer_prospect_type, update_modified=True)

        # Log successful visit creation
        frappe.log_error(
            title="Create Farmer Revisit - Visit Created",
            message={
                "visit_id": visit.name,
                "visit_data": visit.as_dict()
            }
        )

        frappe.db.commit()

        frappe.local.response['http_status_code'] = 201
        return {
            "success": True,
            "status": "success",
            "message": "Visit record created successfully",
            "code": "VISIT_CREATED",
            "data": {
                "visit_id": visit.name,
                "farmer_id": farmer_id
            },
            "http_status_code": 201
        }

    except Exception as e:
        frappe.log_error(
            title="Create Farmer Revisit - Error",
            message={
                "error": str(e),
                "farmer_id": farmer_id,
                "farmer_prospect_type": farmer_prospect_type,
                "previous_visit_id": previous_visit_id,
                "visit_tracker_detail": visit_tracker_detail,
                "traceback": frappe.get_traceback()
            }
        )
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
            "Farmer Detail",
            filters={"assigned_sales_person": employee},
            fields=[
                "name",
                "first_name",
                "last_name",
                "contact_number",
                "village",
                "mandal",
                "district",
                "state",
                "pincode",
                "prospect_type",
                "bmc",
                "age"
            ],
            limit_page_length=None
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
        total_farmers = frappe.db.count("Farmer Detail", filters=filters)
        
        # Get farmers with pagination
        farmers = frappe.get_all(
            "Farmer Detail",
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
        farmer = frappe.get_doc("Farmer Detail", farmer_id)
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
                        "Farmer Detail",
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
        
        # Update farmer detail
        farmer.update(update_fields)
        farmer.save()
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Farmer detail updated successfully",
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
        return handle_error_response(e, "Error updating farmer detail")

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
            # Get farmer detail
            farmer_doc = frappe.get_doc("Farmer Detail", visit.farmer)
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
            order_by="revisit_on asc",  # Order by revisit date
            limit_page_length=None
        )
        
        # Get additional details for each visit
        for visit in visits:
            # Get farmer detail
            farmer_doc = frappe.get_doc("Farmer Detail", visit.farmer)
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
        period: str (optional) - 'all', 'this_month', 'this_quarter', 'this_year', 'last_year'
                                (default: 'this_month')
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get period from query params
        period = frappe.request.args.get('period', 'this_month')
        
        # Get current date
        today = frappe.utils.today()
        
        # Calculate date range based on period
        if period == 'all':
            start_date = None
            end_date = None
        elif period == 'this_month':
            start_date = frappe.utils.get_first_day(today)
            end_date = frappe.utils.get_last_day(today)
        elif period == 'this_quarter':
            start_date = frappe.utils.data.get_quarter_start(today)
            end_date = frappe.utils.data.get_quarter_ending(today)
        elif period == 'this_year':
            start_date = frappe.utils.data.get_year_start(today)
            end_date = frappe.utils.data.get_year_ending(today)
        elif period == 'last_year':
            last_year = frappe.utils.add_years(today, -1)
            start_date = frappe.utils.data.get_year_start(last_year)
            end_date = frappe.utils.data.get_year_ending(last_year)
        else:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Invalid period. Use 'all', 'this_month', 'this_quarter', 'this_year', or 'last_year'",
                "code": "INVALID_PERIOD",
                "http_status_code": 400
            }
        
        # Base filters
        base_filters = {
            "assigned_sales_person": employee,
        }
        
        # Add date filters if period is not 'all'
        if start_date and end_date:
            base_filters["modified"] = ["between", [start_date, end_date]]
        
        # Get total farmers count
        total_farmers = len(frappe.get_all(
            "Farmer Detail",
            filters=base_filters,
            fields=["name"]
        ))

        # Get prospect type counts
        prospect_types = ["Hot", "Warm", "Cold", "Lost", "Converted"]
        prospect_counts = {}
        
        for prospect_type in prospect_types:
            filters = base_filters.copy()
            filters["prospect_type"] = prospect_type
            count = len(frappe.get_all(
                "Farmer Detail",
                filters=filters,
                fields=["name"]
            ))
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
                "period": period,
                "date_range": {
                    "start_date": str(start_date) if start_date else None,
                    "end_date": str(end_date) if end_date else None
                }
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving prospect statistics")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_today_visits() -> Dict[str, Any]:
    """
    Returns list of visits made by the logged-in employee for today
    Required header: Authorization Bearer token
    Query params:
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
        
        # Get today's date
        today = frappe.utils.today()
        
        # Get filter parameters
        visit_type = frappe.request.args.get('visit_type')
        village = frappe.request.args.get('village')
        requested_revisit = frappe.request.args.get('requested_revisit')
        is_revisit = frappe.request.args.get('is_revisit')
        farmer = frappe.request.args.get('farmer')

        # Get today's date range
        today_start = frappe.utils.now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = frappe.utils.now_datetime().replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Build filters
        filters = {
            "visited_by": employee,
            "docstatus": 1,  # Only get submitted documents
            "visit_date": ["between", [today_start, today_end]]  # Only get today's visits
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
        
        # Get visits
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
            order_by="creation desc",
            limit_page_length=None
        )
        
        # Get additional details for each visit
        for visit in visits:
            # Get farmer detail
            farmer_doc = frappe.get_doc("Farmer Detail", visit.farmer)
            visit["farmer_name"] = f"{farmer_doc.first_name} {farmer_doc.last_name}"
            
            # Get village name if village exists
            if visit.village:
                village_doc = frappe.get_doc("Village", visit.village)
                visit["village_name"] = village_doc.village_name
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Today's visits list retrieved successfully",
            "code": "TODAYS_VISITS_RETRIEVED",
            "data": {
                "visits": visits,
                "date": today
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving today's visits list")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_farmer_details() -> Dict[str, Any]:
    """
    Returns detailed information about a specific farmer
    Required header: Authorization Bearer token
    Query params:
        farmer_id: str - The ID of the farmer to retrieve details for
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get farmer_id from query params
        farmer_id = frappe.request.args.get('farmer_id')
        
        if not farmer_id:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "farmer_id is required",
                "code": "MISSING_FARMER_ID",
                "http_status_code": 400
            }
        
        # Check if farmer exists and belongs to the logged-in employee
        farmer = frappe.get_all(
            "Farmer Detail",
            filters={
                "name": farmer_id,
                "assigned_sales_person": employee
            },
            fields=["*"]
        )
        
        if not farmer:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "Farmer not found or not assigned to you",
                "code": "FARMER_NOT_FOUND",
                "http_status_code": 404
            }
        
        farmer = farmer[0]
        
        # Get village name if village exists
        if farmer.village:
            village_doc = frappe.get_doc("Village", farmer.village)
            farmer["village_name"] = village_doc.village_name
        
        # Get BMC name if BMC exists
        if farmer.bmc:
            bmc_doc = frappe.get_doc("BMC", farmer.bmc)
            farmer["bmc_name"] = bmc_doc.bmc_name
        
        # Get all visits for this farmer
        visits = frappe.get_all(
            "Visit Tracker",
            filters={
                "farmer": farmer_id,
                "docstatus": 1  # Only get submitted documents
            },
            fields=[
                "name",
                "visit_date",
                "visit_type",
                "village",
                "requested_revisit",
                "is_revisit",
                "visit_reason",
                "comments",
                "follow_up_visit"
            ],
            order_by="visit_date desc"
        )
        
        # Get village names for visits
        for visit in visits:
            if visit.village:
                village_doc = frappe.get_doc("Village", visit.village)
                visit["village_name"] = village_doc.village_name
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Farmer detail retrieved successfully",
            "code": "FARMER_DETAILS_RETRIEVED",
            "data": {
                "farmer": farmer,
                "visits": visits
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving farmer detail")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_farmer_pending_revisits() -> Dict[str, Any]:
    """
    Returns list of all pending revisits for a specific farmer
    Required header: Authorization Bearer token
    Query params:
        farmer_id: str - The ID of the farmer to retrieve pending revisits for
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
        
        # Get farmer_id from query params
        farmer_id = frappe.request.args.get('farmer_id')
        
        if not farmer_id:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "farmer_id is required",
                "code": "MISSING_FARMER_ID",
                "http_status_code": 400
            }
        
        # Check if farmer exists and belongs to the logged-in employee
        farmer = frappe.get_all(
            "Farmer Detail",
            filters={
                "name": farmer_id
            },
            fields=["name", "first_name", "last_name", "contact_number", "prospect_type"],
            limit_page_length=None
        )
        
        if not farmer:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "Farmer not found or not assigned to you",
                "code": "FARMER_NOT_FOUND",
                "http_status_code": 404
            }
        
        farmer = farmer[0]
        
        # Get pending revisits
        visits = frappe.get_all(
            "Visit Tracker",
            filters={
                "visited_by": employee,
                "farmer": farmer_id,
                "docstatus": 1,  # Only submitted documents
                "requested_revisit": 1,  # Only visits that requested revisit
                "follow_up_visit": ("is", "not set")  # No follow-up visit created yet
            },
            fields=[
                "name",
                "visit_date",
                "visit_type",
                "village",
                "revisit_on",
                "visit_reason",
                "comments"
            ],
            order_by="revisit_on asc",  # Order by revisit date
            limit_page_length=None
        )
        
        # Get village names for visits
        for visit in visits:
            if visit.village:
                village_doc = frappe.get_doc("Village", visit.village)
                visit["village_name"] = village_doc.village_name
        
        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Farmer's pending revisits retrieved successfully",
            "code": "FARMER_REVISITS_RETRIEVED",
            "data": {
                "farmer": {
                    "id": farmer.name,
                    "name": f"{farmer.first_name} {farmer.last_name}",
                    "contact_number": farmer.contact_number,
                    "prospect_type": farmer.prospect_type
                },
                "visits": visits
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving farmer's pending revisits")
    
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_all_pending_revisits_with_farmer_details() -> Dict[str, Any]:
    """
    Returns list of all pending revisits with all farmer details
    Required header: Authorization Bearer token
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result
        
        employee = result["employee"]
                
        # Get pending revisits
        visits = frappe.get_all(
            "Visit Tracker",
            filters={
                "visited_by": employee,
                "docstatus": 1,  # Only submitted documents
                "requested_revisit": 1,  # Only visits that requested revisit
                "follow_up_visit": ("is", "not set")  # No follow-up visit created yet
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
            order_by="revisit_on asc",  # Order by revisit date
            limit_page_length=None
        )
        
        # Get village names for visits
        for visit in visits:
            if visit.village:
                village_doc = frappe.get_doc("Village", visit.village)
                visit["village_name"] = village_doc.village_name
        
        # Now we will get all the farmer details for those visits
        farmer_id_list = list(set([visit.farmer for visit in visits]))  # Get unique farmer IDs
        
        # Get farmer details
        farmers = frappe.get_all(
            "Farmer Detail",
            filters={"name": ["in", farmer_id_list]},
            fields=["name", "first_name", "last_name", "contact_number", "prospect_type"],
            limit_page_length=None
        )
        
        # Format farmer details as requested
        formatted_farmers = [
            {
                "id": farmer.name,
                "first_name": farmer.first_name,
                "last_name": farmer.last_name,
                "name": f"{farmer.first_name} {farmer.last_name}",
                "contact_number": farmer.contact_number,
                "prospect_type": farmer.prospect_type
            }
            for farmer in farmers
        ]

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Farmer's pending revisits retrieved successfully",
            "code": "FARMER_REVISITS_RETRIEVED",
            "data": {
                "farmers" : formatted_farmers, 
                "visits": visits
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving farmer's pending revisits")

