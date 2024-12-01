import frappe
from frappe import _
from datetime import datetime

@frappe.whitelist()
def get_all_employees():
    """
    Get all employees active employees with specified fields
    """
    try:
        # Get all employees with specified fields
        employees = frappe.get_all(
            "Employee",
            fields=[
                "name",
                "owner",
                "creation",
                "modified",
                "modified_by",
                "docstatus",
                "idx",
                "employee",
                "first_name",
                "middle_name",
                "last_name",
                "gender as Gender",
                "date_of_joining",
                "date_of_birth",
                "naming_series",
                "status",
                "custom_point",
                "custom_employee_id",
                "company",
                "custom_device"
            ],
            filters=[
                ["status", "=", "Active"]
            ]
        )
        
        # Format dates to match the schema
        for employee in employees:
            for date_field in ['creation', 'modified', 'date_of_joining', 'date_of_birth']:
                if employee.get(date_field):
                    employee[date_field] = employee[date_field].strftime('%Y-%m-%d')
            
            # Ensure nullish fields are properly handled
            for nullable_field in ['middle_name', 'last_name', 'custom_point']:
                if not employee.get(nullable_field):
                    employee[nullable_field] = None

        return {
            "message": "Employees retrieved successfully",
            "data": employees
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_all_employees: {str(e)}")
        return {
            "message": _("Error retrieving employees"),
            "error": str(e)
        }

def get_all_inactive_or_left_employees_having_device_id():
    """
    Get all inactive or left employees having device id
    """
    try:
        # Get all employees with specified fields
        employees = frappe.get_all(
            "Employee",
            fields=[
                "name",
                "owner",
                "creation",
                "modified",
                "modified_by",
                "docstatus",
                "idx",
                "employee",
                "first_name",
                "middle_name",
                "last_name",
                "gender as Gender",
                "date_of_joining",
                "date_of_birth",
                "naming_series",
                "status",
                "custom_point",
                "custom_employee_id",
                "company",
                "custom_device"
            ],
            filters=[
                ["status", "in", ["Inactive", "Left"]],
                ["custom_device", "!=", None]
            ]
        )
        
        # Format dates to match the schema
        for employee in employees:
            for date_field in ['creation', 'modified', 'date_of_joining', 'date_of_birth']:
                if employee.get(date_field):
                    employee[date_field] = employee[date_field].strftime('%Y-%m-%d')
            
            # Ensure nullish fields are properly handled
            for nullable_field in ['middle_name', 'last_name', 'custom_point']:
                if not employee.get(nullable_field):
                    employee[nullable_field] = None

        return {
            "message": "Employees retrieved successfully",
            "data": employees
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_all_employees: {str(e)}")
        return {
            "message": _("Error retrieving employees"),
            "error": str(e)
        }

@frappe.whitelist(methods=['POST'])
def create_employee():
    try:
        # Verify request method
        if frappe.request.method != "POST":
            frappe.throw(_("Only POST requests are allowed"), frappe.PermissionError)

        # Get JSON data from request
        data = frappe.request.get_json()
        
        # Create new Employee document
        employee = frappe.new_doc("Employee")
        
        # Map the incoming data to employee fields
        field_mappings = {
            "first_name": data.get("first_name"),
            "middle_name": data.get("middle_name"),
            "last_name": data.get("last_name"),
            "gender": data.get("Gender"),  # Note: frontend sends "Gender", backend uses "gender"
            "date_of_joining": data.get("date_of_joining"),
            "date_of_birth": data.get("date_of_birth"),
            "custom_employee_id": data.get("custom_employee_id"),
            "custom_point": data.get("custom_point"),
            "status": data.get("status"),
            "company": data.get("company"),
            "custom_device": data.get("custom_device"),
            "naming_series": data.get("naming_series", "HR-EMP-")
        }

        # Validate required fields
        required_fields = ['first_name', 'custom_employee_id', 'company']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            frappe.throw(
                _("Missing required fields: {}").format(", ".join(missing_fields)),
                frappe.MandatoryError
            )

        # Set values in the document
        for field, value in field_mappings.items():
            if value is not None:  # Only set non-null values
                employee.set(field, value)

        # Save the document
        employee.insert()
        frappe.db.commit()

        return {
            "message": "Employee created successfully",
            "data": {
                "name": employee.name,
                "employee": employee.employee
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error in create_employee: {str(e)}")
        return {
            "message": _("Error creating employee"),
            "error": str(e)
        }


        return {
            "message": "Employee created successfully",
            "data": {
                "name": employee.name,
                "employee": employee.employee
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error in create_employee: {str(e)}")
        return {
            "message": _("Error creating employee"),
            "error": str(e)
        }

@frappe.whitelist(methods=['POST'])
def update_employee_ids():
    try:
        # Get JSON data from request
        data = frappe.request.get_json()
        
        # Validate if data is a list
        if not isinstance(data, list):
            frappe.throw(_("Request data must be an array of objects"), frappe.ValidationError)
        
        # Validate each object in the array
        for item in data:
            if not isinstance(item, dict) or 'name' not in item or 'custom_employee_id' not in item:
                frappe.throw(_("Each object must contain 'name' and 'custom_employee_id'"), frappe.ValidationError)
        
            # Validate custom_device if present
            if 'custom_device' in item and item['custom_device']:
                if not frappe.db.exists('Devices', {'name': item['custom_device']}):
                    frappe.throw(
                        _("Device {} not found in devices").format(item['custom_device']),
                        frappe.ValidationError
                    )

        # Check for duplicate names in request
        names = [item['name'] for item in data]
        if len(names) != len(set(names)):
            frappe.throw(_("Duplicate names found in request"), frappe.ValidationError)
        
        # Check for duplicate employee_ids in request
        employee_ids = [item['custom_employee_id'] for item in data]
        if len(employee_ids) != len(set(employee_ids)):
            frappe.throw(_("Duplicate employee_ids found in request"), frappe.ValidationError)
        
        # Validate all employees exist before updating any
        non_existent_employees = []
        for item in data:
            if not frappe.db.exists('Employee', {'name': item['name']}):
                non_existent_employees.append(item['name'])
        
        if non_existent_employees:
            frappe.throw(
                _("Following employees not found: {}").format(", ".join(non_existent_employees)),
                frappe.ValidationError
            )
        
        # Check if any of the new employee_ids already exist in database
        existing_employee_ids = frappe.db.sql("""
            SELECT custom_employee_id 
            FROM `tabEmployee` 
            WHERE custom_employee_id IN %(employee_ids)s 
            AND name NOT IN %(names)s
        """, {
            'employee_ids': employee_ids,
            'names': names
        }, as_dict=1)
        
        if existing_employee_ids:
            duplicate_ids = [d.custom_employee_id for d in existing_employee_ids]
            frappe.throw(
                _("Following employee_ids already exist: {}").format(", ".join(duplicate_ids)),
                frappe.ValidationError
            )
        
        # If we reach here, all validations passed
        updated_employees = []
        
        # Now safe to update all employees
        for item in data:
            doc = frappe.get_doc('Employee', item['name'])
            doc.custom_employee_id = item['custom_employee_id']

            # Handle custom_device field
            if 'custom_device' in item:
                doc.custom_device = item['custom_device'] if item['custom_device'] else None

            doc.save()
            
            updated_employees.append({
                'name': item['name'],
                'custom_employee_id': item['custom_employee_id'],
                'custom_device': doc.custom_device
            })
        
        frappe.db.commit()
        
        return {
            'status': 'success',
            'message': 'Employee IDs updated successfully',
            'data': {
                'updated': updated_employees
            }
        }
        
    except frappe.ValidationError as e:
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 400
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Employee Update Failed'))
        return {
            'status': 'error',
            'message': str(e),
            'http_status_code': 500
        }