import frappe
from frappe import _
from typing import Dict, Any, List
from .attendance_api import verify_dp_token, handle_error_response
from .farmer_visit_api import handle_base64_image

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_field_options() -> Dict[str, Any]:
    """
    Dynamically returns all select field options for Village Survey and its child tables
    Required header: Authorization Bearer token
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result

        options = {}
        
        # Get Village Survey options
        try:
            survey_meta = frappe.get_meta("Village Survey")
            competitor_meta = frappe.get_meta("Village Survey Competitive Dairy Pricing")
        except Exception as e:
            frappe.log_error(
                title="Get Field Options - DocType Error",
                message={"error": str(e)}
            )
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "Required DocTypes not found",
                "code": "DOCTYPE_NOT_FOUND",
                "http_status_code": 404
            }

        # Get main form select fields
        survey_options = {}
        select_fields = [field for field in survey_meta.fields if field.fieldtype == "Select"]
        for field in select_fields:
            if field.options:
                field_options = [opt for opt in field.options.split('\n') if opt]
                survey_options[field.fieldname] = field_options
        
        # Get competitor table select fields
        competitor_options = {}
        select_fields = [field for field in competitor_meta.fields if field.fieldtype == "Select"]
        for field in select_fields:
            if field.options:
                field_options = [opt for opt in field.options.split('\n') if opt]
                competitor_options[field.fieldname] = field_options

        options = {
            "village_survey": survey_options,
            "competitor_pricing": competitor_options
        }

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
        frappe.log_error(
            title="Get Field Options - Error",
            message={"error": str(e), "traceback": frappe.get_traceback()}
        )
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving field options")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_competitor_companies() -> Dict[str, Any]:
    """
    Returns list of all competitor dairy companies
    Required header: Authorization Bearer token
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result

        # Get all competitor companies
        companies = frappe.get_all(
            "Competitive Dairy Companies",
            fields=["name", "company_name"],
            order_by="company_name"
        )

        if not companies:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "No competitor companies found",
                "code": "NO_COMPETITORS_FOUND",
                "http_status_code": 404
            }

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Competitor companies retrieved successfully",
            "code": "COMPETITORS_RETRIEVED",
            "data": companies,
            "http_status_code": 200
        }

    except Exception as e:
        frappe.log_error(
            title="Get Competitor Companies - Error",
            message={"error": str(e), "traceback": frappe.get_traceback()}
        )
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving competitor companies")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_survey_image() -> Dict[str, Any]:
    """
    Uploads a survey image and returns the file URL
    Required header: Authorization Bearer token
    Body: 
        image: Base64 encoded image string
        survey_id: ID of the village survey (optional, for existing surveys)
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result

        request_data = frappe.request.get_json()
        image_data = request_data.get('image')
        survey_id = request_data.get('survey_id')

        if not image_data:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "Image data is required",
                "code": "IMAGE_REQUIRED",
                "http_status_code": 400
            }

        # If survey_id is provided, verify it exists
        if survey_id:
            if not frappe.db.exists("Village Survey", survey_id):
                frappe.local.response['http_status_code'] = 404
                return {
                    "success": False,
                    "status": "error",
                    "message": "Survey not found",
                    "code": "SURVEY_NOT_FOUND",
                    "http_status_code": 404
                }

        # Add survey_id to the prefix if available
        prefix = f"survey_{survey_id}" if survey_id else "survey"
        image_result = handle_base64_image(image_data, prefix=prefix)
        
        # If survey_id exists, update the document with the new image URL
        if survey_id:
            try:
                survey = frappe.get_doc("Village Survey", survey_id)
                survey.survey_image_url = image_result["file_url"]
                survey.save()
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(
                    title="Upload Survey Image - Update Error",
                    message={"error": str(e), "survey_id": survey_id}
                )
                # Continue anyway as we still have the uploaded image URL

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Image uploaded successfully",
            "code": "IMAGE_UPLOADED",
            "data": {
                "file_url": image_result["file_url"],
                "survey_id": survey_id
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.log_error(
            title="Upload Survey Image - Error",
            message={"error": str(e), "traceback": frappe.get_traceback()}
        )
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error uploading image")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_village_survey(
    survey_data: Dict[str, Any],
    competitor_details: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Creates a new village survey with competitor details
    Required header: Authorization Bearer token
    Body: 
        survey_data: JSON object containing survey data (including optional survey_image_url)
        competitor_details: List of competitor pricing details
    """
    frappe.db.begin()
    
    try:
        # Log incoming request data
        frappe.log_error(
            title="Create Village Survey - Request Data",
            message={
                "survey_data": survey_data,
                "competitor_details": competitor_details
            }
        )

        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.db.rollback()
            frappe.local.response['http_status_code'] = 401
            return result

        # Remove image handling section since it's now handled separately
        # Just use the provided image URL if it exists
        if "survey_image" in survey_data:
            frappe.log_error(
                title="Create Village Survey - Warning",
                message="Deprecated: survey_image field used. Please use survey_image_url instead."
            )
            del survey_data["survey_image"]

        # Prepare competitor details if provided
        if competitor_details:
            survey_data["competitor_details"] = []
            for competitor in competitor_details:
                # Validate required fields
                required_fields = ["company_name", "pricing_type", "price_per_litre", "has_direct_sales"]
                missing_fields = [field for field in required_fields if field not in competitor]
                if missing_fields:
                    frappe.db.rollback()
                    frappe.local.response['http_status_code'] = 400
                    return {
                        "success": False,
                        "status": "error",
                        "message": f"Missing required fields for competitor: {', '.join(missing_fields)}",
                        "code": "MISSING_COMPETITOR_FIELDS",
                        "http_status_code": 400
                    }
                survey_data["competitor_details"].append(competitor)

        # Create village survey document
        survey = frappe.get_doc({
            "doctype": "Village Survey",
            **survey_data
        })
        
        survey.insert()
        survey.submit()  # Since it's a submittable document
        
        # Log successful creation
        frappe.log_error(
            title="Create Village Survey - Success",
            message={
                "survey_id": survey.name,
                "survey_data": survey.as_dict()
            }
        )

        frappe.db.commit()

        frappe.local.response['http_status_code'] = 201
        return {
            "success": True,
            "status": "success",
            "message": "Village survey created successfully",
            "code": "SURVEY_CREATED",
            "data": {
                "name": survey.name,
                "village_name": survey.village_name
            },
            "http_status_code": 201
        }

    except Exception as e:
        frappe.log_error(
            title="Create Village Survey - Error",
            message={
                "error": str(e),
                "survey_data": survey_data,
                "competitor_details": competitor_details,
                "traceback": frappe.get_traceback()
            }
        )
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error creating village survey")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_village_surveys() -> Dict[str, Any]:
    """
    Returns list of village surveys based on filters
    Required header: Authorization Bearer token
    Query params:
        village: str (optional) - Filter by village name
        prospect_type: str (optional) - Filter by prospect type
        from_date: str (optional) - Filter by creation date (YYYY-MM-DD)
        to_date: str (optional) - Filter by creation date (YYYY-MM-DD)
        page: int (optional) - Page number for pagination (default: 1)
        page_size: int (optional) - Items per page (default: 20)
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result

        # Get query parameters
        village = frappe.request.args.get('village')
        prospect_type = frappe.request.args.get('prospect_type')
        from_date = frappe.request.args.get('from_date')
        to_date = frappe.request.args.get('to_date')
        page = int(frappe.request.args.get('page', 1))
        page_size = int(frappe.request.args.get('page_size', 20))

        # Build filters
        filters = {"docstatus": 1}  # Only get submitted documents
        if village:
            filters["village_name"] = village
        if prospect_type:
            filters["village_prospect_type"] = prospect_type
        if from_date:
            filters["creation"] = [">=", from_date]
        if to_date:
            filters["creation"] = ["<=", to_date]

        # Calculate pagination
        start = (page - 1) * page_size
        
        # Get total count for pagination
        total_surveys = frappe.get_all(
            "Village Survey",
            filters=filters,
            as_list=True
        )
        total_count = len(total_surveys)

        # Get surveys with pagination
        surveys = frappe.get_all(
            "Village Survey",
            filters=filters,
            fields=[
                "name",
                "village_name",
                "village_prospect_type",
                "existing_dairy_farms",
                "dairy_farmers_count",
                "new_interested_farmers",
                "total_milk_qty",
                "has_ngo_fpo_sfg",
                "creation",
                "modified"
            ],
            start=start,
            page_length=page_size,
            order_by="creation desc"
        )

        # Get additional details for each survey
        for survey in surveys:
            # Get village details
            village_doc = frappe.get_doc("Village", survey.village_name)
            survey["village_details"] = {
                "mandal": village_doc.mandal,
                "district": village_doc.district
            }

            # Get competitor count
            competitor_count = frappe.get_all(
                "Village Survey Competitive Dairy Pricing",
                filters={"parent": survey.name},
                as_list=True
            )
            survey["competitor_count"] = len(competitor_count)

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Village surveys retrieved successfully",
            "code": "SURVEYS_RETRIEVED",
            "data": {
                "surveys": surveys,
                "pagination": {
                    "total_count": total_count,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "current_page": page
                }
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.log_error(
            title="Get Village Surveys - Error",
            message={
                "error": str(e),
                "filters": frappe.request.args,
                "traceback": frappe.get_traceback()
            }
        )
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving village surveys")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_village_survey_detail() -> Dict[str, Any]:
    """
    Returns detailed information about a specific village survey
    Required header: Authorization Bearer token
    Query params:
        survey_id: str - The ID of the survey to retrieve details for
    """
    try:
        # Verify authorization
        is_valid, result = verify_dp_token(frappe.request.headers)
        if not is_valid:
            frappe.local.response['http_status_code'] = 401
            return result

        # Get survey_id from query params
        survey_id = frappe.request.args.get('survey_id')
        
        if not survey_id:
            frappe.local.response['http_status_code'] = 400
            return {
                "success": False,
                "status": "error",
                "message": "survey_id is required",
                "code": "MISSING_SURVEY_ID",
                "http_status_code": 400
            }

        # Get survey details
        survey = frappe.get_all(
            "Village Survey",
            filters={
                "name": survey_id,
                "docstatus": 1  # Only get submitted documents
            },
            fields=["*"]
        )

        if not survey:
            frappe.local.response['http_status_code'] = 404
            return {
                "success": False,
                "status": "error",
                "message": "Survey not found",
                "code": "SURVEY_NOT_FOUND",
                "http_status_code": 404
            }

        survey = survey[0]

        # Get village details
        if survey.village_name:
            village_doc = frappe.get_doc("Village", survey.village_name)
            survey["village_details"] = {
                "village_name": village_doc.village_name,
                "mandal": village_doc.mandal,
                "district": village_doc.district
            }

        # Get competitor details
        competitor_details = frappe.get_all(
            "Village Survey Competitive Dairy Pricing",
            filters={"parent": survey_id},
            fields=[
                "company_name",
                "pricing_type",
                "price_per_litre",
                "has_direct_sales"
            ]
        )

        # Get company names for competitors
        for competitor in competitor_details:
            company_doc = frappe.get_doc("Competitive Dairy Companies", competitor.company_name)
            competitor["company_name_display"] = company_doc.company_name

        frappe.local.response['http_status_code'] = 200
        return {
            "success": True,
            "status": "success",
            "message": "Village survey details retrieved successfully",
            "code": "SURVEY_DETAILS_RETRIEVED",
            "data": {
                "survey": survey,
                "competitor_details": competitor_details
            },
            "http_status_code": 200
        }

    except Exception as e:
        frappe.log_error(
            title="Get Village Survey Detail - Error",
            message={
                "error": str(e),
                "survey_id": survey_id,
                "traceback": frappe.get_traceback()
            }
        )
        frappe.local.response['http_status_code'] = 500
        return handle_error_response(e, "Error retrieving village survey details")

