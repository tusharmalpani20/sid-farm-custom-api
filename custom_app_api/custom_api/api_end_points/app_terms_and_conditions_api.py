import frappe
from frappe import _
from frappe.utils import cint, now_datetime
import json

@frappe.whitelist(allow_guest=True)
def get_app_terms_and_conditions():
    try:
        # Get app_name from query parameters
        app_name = frappe.request.args.get('app_name')
        
        # Validate app_name
        if not app_name:
            frappe.throw(_("Missing required parameter: app_name"), frappe.MandatoryError)
            
        # Hardcoded terms and conditions for each app
        terms_mapping = {
            'SF Partner': {
                'type': 'text',
                'tac': '''
                1. Delivery Partner: You are engaged as a delivery partner, not an employee of Sids Farm Private Limited.
                2. Responsibilities: You agree to deliver orders professionally, promptly, and in compliance with local regulations.
                3. Permissions: You consent to grant the ERP application access to your device's location, contacts, and gallery, as required for tracking deliveries, communicating with customers, and uploading relevant images or documents.
                4. Payment: Payments will be made per completed delivery or as specified in the payment schedule. Penalties may apply for non-compliance or delays.
                5. Data Privacy: You agree to handle all customer and company data confidentially and as per our privacy policy.
                6. Termination: The Company reserves the right to terminate this agreement immediately for breach of terms or poor performance.
                '''
            },
            'SF Field Force': {
                'type': 'link',
                'tac': 'https://example.com/field-force-terms'
            }
        }
        
        if app_name not in terms_mapping:
            frappe.throw(
                _("Invalid app_name. Must be one of: {}").format(", ".join(terms_mapping.keys())),
                frappe.ValidationError
            )
            
        return {
            'status': 'success',
            'message': 'Terms and conditions retrieved successfully',
            'data': terms_mapping[app_name],
            'http_status_code': 200
        }
        
    except frappe.ValidationError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 400
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Failed to retrieve terms and conditions'))
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 500
        }


    try:
        # Verify request method
        if frappe.request.method != "PUT":
            frappe.throw(_("Only PUT requests are allowed"), frappe.PermissionError)

        # Get JSON data from request
        data = frappe.request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            frappe.throw(_("Missing required field: name"), frappe.MandatoryError)

        # Check if device exists
        if not frappe.db.exists('Devices', data['name']):
            frappe.throw(
                _("Device with name {} does not exist").format(data['name']),
                frappe.DoesNotExistError
            )

        # Get the existing device document
        doc = frappe.get_doc('Devices', data['name'])

        # Update fields if provided in the request
        updateable_fields = [
            'device_id', 'device_f_name', 'device_s_name', 'device_direction', 
            'serial_number', 'connection_type', 'ip_address', 'device_type', 
            'last_ping', 'is_real_time', 'device_vendor', 'device_info', 
            'user_count', 'f_p_count', 'device_model', 'server_url', 'point'
        ]

        for field in updateable_fields:
            if field in data:
                if field == 'device_id' and data[field] != doc.device_id:
                    # Check if new device_id is unique
                    if frappe.db.exists('Devices', {'device_id': data[field]}):
                        frappe.throw(
                            _("Device with ID {} already exists").format(data[field]),
                            frappe.DuplicateEntryError
                        )
                if field == 'is_real_time':
                    doc.is_real_time = cint(data[field])
                elif field in ['user_count', 'f_p_count']:
                    setattr(doc, field, cint(data[field]))
                elif field == 'device_info':
                    if isinstance(data[field], str):
                        json.loads(data[field])  # Validate JSON
                        doc.device_info = data[field]
                    elif isinstance(data[field], dict):
                        doc.device_info = json.dumps(data[field])
                    else:
                        raise ValueError("device_info must be a valid JSON object")
                elif field == 'point':
                    if data[field] and not frappe.db.exists('Point', data[field]):
                        frappe.throw(
                            _("Point {} does not exist").format(data[field]),
                            frappe.ValidationError
                        )
                    doc.point = data[field]
                else:
                    setattr(doc, field, data[field])

        # Save the updated document
        doc.save()
        frappe.db.commit()
        
        return {
            'status': 'success',
            'message': 'Device updated successfully',
            'data': doc.as_dict()
        }
        
    except frappe.ValidationError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 400
        }
    except frappe.DoesNotExistError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 404
        }
    except frappe.DuplicateEntryError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 409
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Device Update Failed'))
        #print the log error message
        print(frappe.get_traceback())
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 500
        }