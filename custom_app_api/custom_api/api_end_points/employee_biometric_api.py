import frappe
import json
import requests
import logging
from typing import Dict, Any, List, Tuple
from frappe.utils import now_datetime, today
from custom_app_api.custom_api.api_end_points.attendance_api import (
    verify_dp_token,
    validate_employee_location,
    calculate_distance
)

# Configuration
BIOMETRIC_SERVER_URL = "http://localhost:8050"
REQUIRED_IMAGE_COUNT = 4

# Configure logging
logger = logging.getLogger(__name__)

@frappe.whitelist(allow_guest=True, methods=["POST"])
def register_face_biometric() -> Dict[str, Any]:
    """Register facial biometric data for an employee"""
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 500)
            return result

        # Validate request body
        if not frappe.request.json:
            return create_error_response(
                code="REQUEST_BODY_REQUIRED",
                message="Request body is required",
                http_status_code=400
            )

        # Extract data
        data = frappe.request.json
        employee = result["employee"]
        images = data.get("images", [])

        # Validate images
        if not isinstance(images, list):
            return create_error_response(
                code="INVALID_IMAGE_FORMAT",
                message="Images must be provided as a list",
                http_status_code=400
            )

        if len(images) != REQUIRED_IMAGE_COUNT:
            return create_error_response(
                code="INVALID_IMAGE_COUNT",
                message=f"Exactly {REQUIRED_IMAGE_COUNT} images are required",
                details={
                    "required_count": REQUIRED_IMAGE_COUNT,
                    "provided_count": len(images)
                },
                http_status_code=400
            )

        # Check for any existing registration (not just active)
        existing_record = frappe.db.get_value(
            "Employee Biometric Master",
            {"employee": employee},
            ["name", "registration_date", "status"],
            as_dict=True
        )

        if existing_record:
            return create_error_response(
                code="BIOMETRIC_REGISTRATION_EXISTS",
                message="Biometric registration already exists for this employee",
                details={
                    "registration_id": existing_record.name,
                    "registration_date": existing_record.registration_date,
                    "status": existing_record.status
                },
                http_status_code=400
            )

        # Call face recognition server
        face_server_response = call_face_recognition_server(images)
        if not face_server_response["success"]:
            return handle_face_server_error(face_server_response)

        # Create biometric record
        try:
            biometric_doc = create_biometric_record(employee, face_server_response)
            logger.info(f"Created biometric registration for employee {employee}")
            
            return create_success_response(
                code="BIOMETRIC_REGISTRATION_SUCCESS",
                message="Biometric data registered successfully",
                data={
                    "registration_id": biometric_doc.name,
                    "employee": biometric_doc.employee,
                    "employee_name": biometric_doc.employee_name,
                    "registration_date": biometric_doc.registration_date,
                    "embeddings_count": biometric_doc.embeddings_count,
                    "models_used": json.loads(biometric_doc.models_used) if biometric_doc.models_used else [],
                    "registration_metrics": face_server_response["data"].get("registration_metrics", {})
                }
            )

        except Exception as e:
            logger.error(f"Failed to create biometric record for {employee}: {str(e)}")
            logger.error(f"Face Server Response: {json.dumps(face_server_response, indent=2)}")
            return create_error_response(
                code="BIOMETRIC_REGISTRATION_FAILED",
                message="Failed to save biometric data",
                details={"error": str(e)},
                http_status_code=500
            )

    except Exception as e:
        logger.error(f"Biometric registration error: {str(e)}")
        return create_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            details={"error": str(e)},
            http_status_code=500
        )

@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_face_biometric() -> Dict[str, Any]:
    """Verify facial biometric data for an employee"""
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 500)
            return result

        # Validate request body
        if not frappe.request.json:
            return create_error_response(
                code="REQUEST_BODY_REQUIRED",
                message="Request body is required",
                http_status_code=400
            )

        # Extract data
        data = frappe.request.json
        employee = result["employee"]
        image = data.get("image")

        logger.info(f"Processing verification for employee: {employee}")

        # Validate required fields
        required_fields = ["image", "latitude", "longitude", "accuracy"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return create_error_response(
                code="MISSING_REQUIRED_FIELDS",
                message=f"Missing required fields: {', '.join(missing_fields)}",
                http_status_code=400
            )

        # Extract location data
        try:
            latitude = float(data.get("latitude"))
            longitude = float(data.get("longitude"))
            accuracy = float(data.get("accuracy"))
        except (TypeError, ValueError):
            return create_error_response(
                code="INVALID_LOCATION_DATA",
                message="Invalid location data format",
                http_status_code=400
            )

        # Validate employee location first
        is_location_valid, location_result = validate_employee_location(employee, latitude, longitude)
        if not is_location_valid:
            frappe.local.response['http_status_code'] = location_result.get("http_status_code", 400)
            return {
                "success": False,
                **location_result
            }

        logger.info(f"Location validated successfully for employee {employee}")

        # Get employee's biometric registration
        biometric_record = frappe.get_value(
            "Employee Biometric Master",
            {
                "employee": employee,
                "status": "Active"
            },
            ["name", "face_embeddings", "models_used"],
            as_dict=True
        )

        if not biometric_record:
            return create_error_response(
                code="NO_BIOMETRIC_REGISTRATION",
                message="No active biometric registration found",
                http_status_code=400
            )

        # Prepare verification request
        try:
            embeddings = json.loads(biometric_record.face_embeddings)
            models_used = json.loads(biometric_record.models_used)
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {str(e)}")
            logger.error(f"Face embeddings raw data: {biometric_record.face_embeddings}")
            return create_error_response(
                code="INVALID_BIOMETRIC_DATA",
                message="Invalid biometric data format",
                http_status_code=500
            )

        # Start transaction for database operations
        frappe.db.begin()
        try:
            # Call verification server
            logger.info("Calling verification server...")
            verification_response = requests.post(
                f"{BIOMETRIC_SERVER_URL}/verify",
                json={
                    "image_base64": image,
                    "embeddings": embeddings
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            verification_response.raise_for_status()
            result = verification_response.json()
            logger.debug(f"Verification server response: {json.dumps(result, indent=2)}")

            # Map status to success
            if "status" in result:
                result["success"] = result["status"] == "success"
            elif not isinstance(result, dict):
                logger.error(f"Invalid response format - not a dictionary: {type(result)}")
                raise ValueError("Invalid response format from verification server")
            else:
                logger.error(f"Missing 'status' key in response: {json.dumps(result, indent=2)}")
                raise ValueError("Invalid response format: missing status information")

            # Create biometric log entry
            log_entry = create_biometric_log(employee, result)
            logger.info(f"Created biometric log entry: {log_entry.name}")
            
            if result["success"] and result.get("data", {}).get("is_match", False):
                # Create attendance record if verification successful
                attendance_data = {
                    "naming_series": "ATT-",
                    "employee": employee,
                    "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
                    "status": "Present",
                    "attendance_date": today(),
                    "company": frappe.db.get_single_value("Global Defaults", "default_company"),
                    "custom_mobile_latitude": latitude,
                    "custom_mobile_longitude": longitude,
                    "custom_mobile_accuracy": accuracy,
                    "custom_attendance_marked_at": frappe.utils.now(),
                    "custom_location_verified": 1,
                    "custom_geofence_data": frappe.as_json(location_result.get("data", {}))
                }

                # Get route information
                employee_doc = frappe.get_doc("Employee", employee)
                if employee_doc.custom_route:
                    attendance_data["custom_route"] = employee_doc.custom_route
                    route_total_delivery = frappe.db.get_value(
                        "Route",
                        employee_doc.custom_route,
                        "total_delivery"
                    )
                    if route_total_delivery:
                        attendance_data["custom_total_deliveries"] = route_total_delivery

                # Check for existing attendance
                existing_attendance = frappe.db.exists("Attendance", {
                    "employee": employee,
                    "attendance_date": today(),
                    "docstatus": ["!=", 2]  # Not cancelled
                })

                if existing_attendance:
                    logger.info(f"Attendance already exists for employee {employee} on {today()}")
                else:
                    # Create attendance
                    attendance = frappe.get_doc({
                        "doctype": "Attendance",
                        **attendance_data
                    })
                    attendance.insert(ignore_permissions=True)
                    logger.info(f"Created attendance record: {attendance.name}")

                    # Create route tracking record for location history
                    route_tracking = frappe.get_doc({
                        "doctype": "Route Tracking",
                        "attendance": attendance.name,
                        "employee": employee,
                        "latitude": latitude,
                        "longitude": longitude,
                        "accuracy": accuracy,
                        "recorded_at": frappe.utils.now()
                    })
                    route_tracking.insert(ignore_permissions=True)
                    logger.info(f"Created route tracking record: {route_tracking.name}")

                # Prepare success response
                response_data = {
                    "verification_id": log_entry.name,
                    "is_match": log_entry.is_match,
                    "confidence_score": log_entry.confidence_score,
                    "liveness_score": log_entry.liveness_score,
                    "attendance_created": not existing_attendance,
                    "attendance_id": attendance.name if not existing_attendance else existing_attendance,
                    "location_data": {
                        "latitude": latitude,
                        "longitude": longitude,
                        "accuracy": accuracy,
                        "verified_point": location_result.get("data", {}),
                        "route": location_result.get("data", {}).get("route")
                    },
                    "route_tracking_id": route_tracking.name if not existing_attendance else None,
                    "validation_details": {
                        "face_detection": json.loads(log_entry.face_detection) if log_entry.face_detection else {},
                        "liveness_detection": json.loads(log_entry.liveness_detection) if log_entry.liveness_detection else {},
                        "model_results": json.loads(log_entry.model_results) if log_entry.model_results else {},
                        "robustness_features": json.loads(log_entry.robustness_features) if log_entry.robustness_features else {}
                    }
                }
                
                frappe.db.commit()
                logger.info("Verification successful, returning response")
                return create_success_response(
                    code="VERIFICATION_SUCCESS",
                    message=result.get("message", "Face verification completed"),
                    data=response_data
                )
            else:
                # Handle verification failure
                frappe.db.commit()
                logger.warning(f"Verification failed: {result.get('message', 'Unknown error')}")
                return create_error_response(
                    code=result.get("code", "VERIFICATION_FAILED"),
                    message=result.get("message", "Face verification failed"),
                    details=result.get("details"),
                    http_status_code=400
                )

        except requests.RequestException as e:
            logger.error(f"Request Exception during verification: {str(e)}")
            frappe.db.rollback()
            raise e
        except Exception as e:
            logger.error(f"Exception during verification process: {str(e)}")
            frappe.db.rollback()
            raise e

    except requests.RequestException as e:
        logger.error(f"Face Verification Error - Service Unavailable: {str(e)}")
        return create_error_response(
            code="FACE_VERIFICATION_SERVICE_ERROR",
            message="Face verification service unavailable",
            details={"error": str(e)},
            http_status_code=502
        )
        
    except Exception as e:
        logger.error(f"Face Verification Error: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error args: {e.args}")
        return create_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            details={"error": str(e)},
            http_status_code=500
        )

@frappe.whitelist(allow_guest=True, methods=["GET"])
def check_user_biometric_registration() -> Dict[str, Any]:
    """Check if user has biometric registration"""
    try:
        # Verify token and authenticate
        is_valid, result = verify_dp_token(frappe.request.headers)
        
        if not is_valid:
            frappe.local.response['http_status_code'] = result.get("http_status_code", 500)
            return result

        # Extract employee from token verification result
        employee = result["employee"]
        logger.info(f"Checking biometric registration for employee: {employee}")

        # Get employee's biometric registration
        biometric_record = frappe.get_value(
            "Employee Biometric Master",
            {
                "employee": employee,
                "status": "Active"
            },
            ["name", "registration_date", "employee_name"],
            as_dict=True
        )

        if not biometric_record:
            return create_error_response(
                code="NO_BIOMETRIC_REGISTRATION",
                message="No active biometric registration found",
                http_status_code=404
            )

        # Return success with registration details
        return create_success_response(
            code="BIOMETRIC_REGISTRATION_FOUND",
            message="Active biometric registration exists",
            data={
                "registration_id": biometric_record.name,
                "registration_date": biometric_record.registration_date,
                "employee": employee,
                "employee_name": biometric_record.employee_name
            }
        )

    except Exception as e:
        logger.error(f"Error checking biometric registration: {str(e)}")
        return create_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred while checking biometric registration",
            details={"error": str(e)},
            http_status_code=500
        )

def check_existing_registration(employee: str) -> Dict:
    """Check if employee already has an active registration"""
    return frappe.db.get_value(
        "Employee Biometric Master",
        {
            "employee": employee,
            "status": "Active"
        },
        ["name", "registration_date"],
        as_dict=True
    )

def call_face_recognition_server(images: List[str]) -> Dict[str, Any]:
    """Call the face recognition server for registration"""
    try:
        response = requests.post(
            f"{BIOMETRIC_SERVER_URL}/register",
            json=images,
            headers={"Content-Type": "application/json"},
            timeout=120  # Increased timeout to 120 seconds for processing multiple images
        )
        
        response.raise_for_status()
        return response.json()
        
    except requests.RequestException as e:
        print(f"Face Recognition Error: {str(e)}")
        return {
            "success": False,
            "status": "error",
            "code": "FACE_RECOGNITION_SERVICE_ERROR",
            "message": "Face recognition service unavailable",
            "details": {"error": str(e)}
        }

def create_biometric_record(employee: str, face_data: Dict) -> Any:
    """Create a new biometric record in Frappe"""
    current_time = now_datetime()
    
    # Extract data from face recognition response
    response_data = face_data["data"]
    embeddings_data = response_data["embeddings_by_model"]
    models_used = response_data["models_used"]
    embeddings_count = response_data["embeddings_count"]
    
    # Get additional metrics if available
    registration_metrics = response_data.get("registration_metrics", {})
    identity_validation = registration_metrics.get("identity_validation", {})
    quality_checks = registration_metrics.get("validation_results", {})
    
    # Create document with extended information
    biometric_doc = frappe.get_doc({
        "doctype": "Employee Biometric Master",
        "employee": employee,
        "face_embeddings": json.dumps(embeddings_data),
        "registration_date": current_time,
        "last_updated": current_time,
        "status": "Active",
        "models_used": json.dumps(models_used),
        "embeddings_count": embeddings_count,
        # Store additional metrics as JSON strings
        "identity_validation": json.dumps(identity_validation) if identity_validation else None,
        "quality_metrics": json.dumps(quality_checks) if quality_checks else None
    })
    
    biometric_doc.insert(ignore_permissions=True)
    return biometric_doc

def create_biometric_log(employee: str, verification_result: Dict) -> Any:
    """Create a biometric verification log entry"""
    current_time = now_datetime()
    
    # Extract verification data
    data = verification_result.get("data", {})
    validation = data.get("validation", {})
    
    # Determine status based on both success and match result
    if verification_result.get("code") in [
        "MULTIPLE_FACES_DETECTED",
        "NO_FACE_DETECTED",
        "IMAGE_QUALITY_ISSUE",
        "LIVENESS_CHECK_FAILED"
    ]:
        status = "Error"
    elif verification_result["success"] and data.get("is_match", False):
        status = "Success"
    else:
        status = "Failed"
    
    # Create log document
    log_doc = frappe.get_doc({
        "doctype": "Employee Biometric Log",
        "employee": employee,
        "verification_date": current_time,
        "status": status,
        "is_match": data.get("is_match", False),
        "confidence_score": data.get("confidence"),
        "liveness_score": data.get("liveness_detection", {}).get("score"),
        "face_detection": json.dumps(validation.get("face_detection", {})),
        "liveness_detection": json.dumps(data.get("liveness_detection", {})),
        "model_results": json.dumps(data.get("model_results", {})),
        "robustness_features": json.dumps(data.get("robustness_features", {})),
        "error_code": verification_result.get("code") if status == "Error" else None,
        "error_message": verification_result.get("message") if status == "Error" else None,
        "error_details": json.dumps(verification_result.get("details", {})) if status == "Error" else None
    })
    
    log_doc.insert(ignore_permissions=True)
    return log_doc

def create_error_response(code: str, message: str, details: Dict = None, http_status_code: int = 500) -> Dict[str, Any]:
    """Create a standardized error response"""
    frappe.local.response['http_status_code'] = http_status_code
    return {
        "success": False,
        "status": "error",
        "code": code,
        "message": message,
        "details": details,
        "http_status_code": http_status_code
    }

def create_success_response(code: str, message: str, data: Dict = None) -> Dict[str, Any]:
    """Create a standardized success response"""
    frappe.local.response['http_status_code'] = 200
    return {
        "success": True,
        "status": "success",
        "code": code,
        "message": message,
        "data": data,
        "http_status_code": 200
    }

def handle_face_server_error(response: Dict) -> Dict[str, Any]:
    """Handle error responses from face recognition server"""
    error_code = response.get("code", "FACE_RECOGNITION_ERROR")
    error_message = response.get("message", "Face recognition failed")
    error_details = response.get("details", {})
    
    # Print detailed error for debugging
    print(f"Face Recognition Error - {error_code}")
    print(f"Message: {error_message}")
    print(f"Details: {json.dumps(error_details, indent=2)}")
    
    # Map face server error codes to appropriate HTTP status codes
    http_status_code = 400 if error_code in [
        "MULTIPLE_FACES_DETECTED",
        "NO_FACE_DETECTED",
        "IMAGE_QUALITY_ISSUE",
        "IDENTITY_MISMATCH",
        "INSUFFICIENT_IMAGES",
        "NO_IMAGES_PROVIDED"
    ] else 500
    
    return create_error_response(
        code=error_code,
        message=error_message,
        details=error_details,
        http_status_code=http_status_code
    )