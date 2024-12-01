import frappe
from frappe import _
from frappe.utils import cint, flt

@frappe.whitelist(methods=['POST'])  # No need for allow_guest=True; it's protected by default
def create_point(parameter = None):
    try:
        # Verify request method
        if frappe.request.method != "POST":
            frappe.throw(_("Only POST requests are allowed"), frappe.PermissionError)

        # Get JSON data from request
        data = frappe.request.get_json()
        
        # Validate required fields
        required_fields = ['point_id', 'point_name', 'point_code']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            frappe.throw(
                _("Missing required fields: {}").format(", ".join(missing_fields)),
                frappe.MandatoryError
            )
        
        # Check if point_name already exists
        if frappe.db.exists('Point', {'point_name': data['point_name']}):
            frappe.throw(
                _("Point with name '{}' already exists").format(data['point_name']),
                frappe.DuplicateEntryError
            )

        # Create new Point document
        doc = frappe.new_doc('Point')
        
        # Set values from request data with null handling
        doc.point_id = data['point_id']  # Required
        doc.point_name = data['point_name']  # Required
        doc.point_code = data['point_code']  # Required
        doc.latitude = flt(data.get('latitude')) if data.get('latitude') is not None else None
        doc.longitude = flt(data.get('longitude')) if data.get('longitude') is not None else None
        doc.radius = flt(data.get('radius')) if data.get('radius') is not None else None
        doc.full_address = data.get('full_address') or None
        doc.is_active = cint(data.get('is_active', 1))  # Defaults to 1 if not provided
        
        # Insert the document
        doc.insert()
        
        frappe.db.commit()  # Commit the transaction
        
        return {
            'status': 'success',
            'message': 'Point created successfully',
            'data': doc.as_dict()
        }
        
    except frappe.MandatoryError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 400  # Bad Request
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Point Creation Failed'))
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 500  # Internal Server Error
        }

@frappe.whitelist(methods=['GET'])
def get_all_points():
    try:
        # Get all Points documents with all fields
        points = frappe.get_all(
            'Point',
            fields=['*']
        )
        
        return {
            'status': 'success',
            'message': 'points retrieved successfully',
            'data': points
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Point Retrieval Failed'))
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 500
        }

@frappe.whitelist(methods=['POST'])
def update_point_ids():
    try:
        # Get JSON data from request
        data = frappe.request.get_json()
        
        # Validate if data is a list
        if not isinstance(data, list):
            frappe.throw(_("Request data must be an array of objects"), frappe.ValidationError)
        
        # Validate each object in the array
        for item in data:
            if not isinstance(item, dict) or 'name' not in item or 'point_id' not in item:
                frappe.throw(_("Each object must contain 'name' and 'point_id'"), frappe.ValidationError)
        
        # Check for duplicate names in request
        names = [item['name'] for item in data]
        if len(names) != len(set(names)):
            frappe.throw(_("Duplicate names found in request"), frappe.ValidationError)
        
        # Check for duplicate point_ids in request
        point_ids = [item['point_id'] for item in data]
        if len(point_ids) != len(set(point_ids)):
            frappe.throw(_("Duplicate point_ids found in request"), frappe.ValidationError)
        
        # Validate all locations exist before updating any
        non_existent_locations = []
        for item in data:
            if not frappe.db.exists('Point', {'name': item['name']}):
                non_existent_locations.append(item['name'])
        
        if non_existent_locations:
            frappe.throw(
                _("Following locations not found: {}").format(", ".join(non_existent_locations)),
                frappe.ValidationError
            )
        
        # Check if any of the new point_ids already exist in database
        # (excluding the points we're updating)
        existing_point_ids = frappe.db.sql("""
            SELECT point_id 
            FROM `tabPoint` 
            WHERE point_id IN %(point_ids)s 
            AND name NOT IN %(names)s
        """, {
            'point_ids': point_ids,
            'names': names
        }, as_dict=1)
        
        if existing_point_ids:
            duplicate_ids = [d.point_id for d in existing_point_ids]
            frappe.throw(
                _("Following point_ids already exist: {}").format(", ".join(duplicate_ids)),
                frappe.ValidationError
            )
        
        # If we reach here, all validations passed
        updated_locations = []
        
        # Now safe to update all locations
        for item in data:
            doc = frappe.get_doc('Point', item['name'])
            doc.point_id = item['point_id']
            doc.save()
            
            updated_locations.append({
                'name': item['name'],
                'point_id': item['point_id']
            })
        
        frappe.db.commit()
        
        return {
            'status': 'success',
            'message': 'Points updated successfully',
            'data': {
                'updated': updated_locations
            }
        }
        
    except frappe.ValidationError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 400
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Point Update Failed'))
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 500
        }
