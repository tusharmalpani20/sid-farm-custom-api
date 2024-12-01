import frappe
from frappe import _
from frappe.utils import cint, now_datetime
import json

@frappe.whitelist(methods=['POST'])
def create_device():
    try:
        # Verify request method
        if frappe.request.method != "POST":
            frappe.throw(_("Only POST requests are allowed"), frappe.PermissionError)

        # Get JSON data from request
        data = frappe.request.get_json()
        
        # Validate required fields
        required_fields = ['device_id', 'device_f_name']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            frappe.throw(
                _("Missing required fields: {}").format(", ".join(missing_fields)),
                frappe.MandatoryError
            )

        # Validate if point exists
        if data.get('point') and not frappe.db.exists('Point', data.get('point')):
            frappe.throw(
                _("Point {} does not exist").format(data.get('point')),
                frappe.ValidationError
            )

        # Validate if device_id is unique
        if frappe.db.exists('Devices', {'device_id': data.get('device_id')}):
            frappe.throw(
                _("Device with ID {} already exists").format(data.get('device_id')),
                frappe.DuplicateEntryError
            )

        # # Validate is_real_time is either 0 or 1        
        #  if 'is_real_time' in data:
        #     if isinstance(data['is_real_time'], bool):
        #         data['is_real_time'] = 1 if data['is_real_time'] else 0
        #     elif data['is_real_time'] not in [0, 1]:
        #         frappe.throw(
        #             _("is_real_time must be a boolean value (true/false) or 0/1"),
        #             frappe.ValidationError
        #         )

        # Validate device_info is valid JSON if provided
        if data.get('device_info'):
            try:
                if isinstance(data['device_info'], str):
                    json.loads(data['device_info'])
                elif not isinstance(data['device_info'], dict):
                    raise ValueError
            except ValueError:
                frappe.throw(
                    _("device_info must be a valid JSON object"),
                    frappe.ValidationError
                )

        # Create new Devices document
        doc = frappe.new_doc('Devices')
        
        # Set values from request data
        doc.device_id = data['device_id']
        doc.device_f_name = data['device_f_name']
        doc.device_s_name = data.get('device_s_name')
        doc.device_direction = data.get('device_direction')
        doc.serial_number = data['serial_number']
        doc.connection_type = data.get('connection_type')
        doc.ip_address = data.get('ip_address')
        doc.device_type = data.get('device_type')
        doc.last_ping = data.get('last_ping')
        doc.is_real_time = cint(data.get('is_real_time', 0))
        doc.device_vendor = data.get('device_vendor')
        
        # Handle device_info JSON field
        if data.get('device_info'):
            if isinstance(data['device_info'], str):
                doc.device_info = data['device_info']
            else:
                doc.device_info = json.dumps(data['device_info'])
        
        doc.user_count = cint(data.get('user_count', 0))
        doc.f_p_count = cint(data.get('f_p_count', 0))
        doc.device_model = data.get('device_model')
        doc.server_url = data.get('server_url')
        doc.point = data['point']
        
        # Insert the document
        doc.insert()
        
        frappe.db.commit()
        
        return {
            'status': 'success',
            'message': 'Device created successfully',
            'data': doc.as_dict()
        }
        
    except frappe.ValidationError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 400
        }
    except frappe.DuplicateEntryError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 409
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Device Creation Failed'))
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 500
        }

@frappe.whitelist(methods=['GET'])
def get_all_devices():
    try:
        # Get all Device documents with all fields
        devices = frappe.get_all(
            'Devices',
            fields=['*']
        )
        return {
            'status': 'success',
            'message': 'Devices retrieved successfully',
            'data': devices
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Device Retrieval Failed'))
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 500
        }

@frappe.whitelist(methods=['PUT'])
def update_device():
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