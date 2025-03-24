import frappe
from frappe.model.document import Document
from frappe import _
import time
import re

class BackupDeliveryPartnerMapping(Document):
    @frappe.whitelist()
    def get_backup_delivery_partners(self):
        try:
            # Get the permission conditions from employee doctype
            permission_conditions = frappe.get_attr("custom_app_api.permission_query_conditions.employee.get_permission_query_conditions")(frappe.session.user)
            
            filters = {
                "designation": "Backup Delivery Partner",
                "status": "Active"
            }
            
            if self.area:
                filters["custom_area"] = self.area
            if self.point:
                filters["custom_point"] = self.point
            if self.zone:
                filters["custom_zone"] = self.zone

            # If there are permission conditions, extract the employee names and add to filters
            if permission_conditions:
                import re
                matches = re.search(r"in \('([^']*)'(?:,'([^']*)')*\)", permission_conditions)
                if matches:
                    employee_list = [x.strip("'") for x in permission_conditions.split("'") if x.strip("', ")]
                    filters['name'] = ['in', employee_list]
            
            employees = frappe.get_all(
                "Employee",
                filters=filters,
                fields=["name", "employee_name", "custom_route", "custom_point", 
                       "custom_area", "custom_zone"]
            )
            
            return employees
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Backup Delivery Partner Error")
            frappe.throw(_("Error fetching delivery partners"))

    def on_submit(self):
        if not self.employees_data:
            return
            
        employee_updates = frappe.parse_json(self.employees_data)
        for emp_data in employee_updates:
            if emp_data.get('route'):
                update_employee_mapping(
                    employee=emp_data.get('employee'),
                    route=emp_data.get('route'),
                    point=emp_data.get('point'),
                    area=emp_data.get('area'),
                    zone=emp_data.get('zone')
                )

@frappe.whitelist()
def update_employee_mapping(employee, route, point, area, zone):
    try:
        doc = frappe.get_doc('Employee', employee)
        
        # Only update if route has changed
        if doc.custom_route != route:

            # Store previous route details
            previous_route = doc.custom_route

            doc.custom_route = route
            # doc.custom_point = point
            # doc.custom_area = area
            # doc.custom_zone = zone
            doc.save(ignore_permissions=False)
            
            return {
                "message": "Employee details updated successfully",
                "status": "success"
            }

            # Create Employee Route Update Tool record
            route_update = frappe.get_doc({
                "doctype": "Employee Route Update Tool",
                "employee": employee,
                "previous_route": previous_route,
                "new_route": route,
                "user": frappe.session.user,
                "updated_at": frappe.utils.now()
            })
            route_update.insert(ignore_permissions=True)
            route_update.submit()
        
        return {
            "message": "No changes detected",
            "status": "success"
        }
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Route Update Error")
        frappe.throw(_("Could not update employee details"))

@frappe.whitelist()
def get_backup_delivery_partners():
    try:
        # Get the permission conditions from employee doctype
        permission_conditions = frappe.get_attr("custom_app_api.permission_query_conditions.employee.get_permission_query_conditions")(frappe.session.user)
        
        filters = {
            'designation': 'Backup Delivery Partner',
            'status': 'Active'
        }

        # If there are permission conditions, extract the employee names and add to filters
        if permission_conditions:
            # Extract employee names from the condition string
            # The condition looks like: "name in ('EMP001','EMP002')"
            import re
            matches = re.search(r"in \('([^']*)'(?:,'([^']*)')*\)", permission_conditions)
            if matches:
                employee_list = [x.strip("'") for x in permission_conditions.split("'") if x.strip("', ")]
                filters['name'] = ['in', employee_list]

        employees = frappe.get_all('Employee',
            filters=filters,
            fields=['name', 'employee_name', 'custom_route', 'custom_point', 
                   'custom_area', 'custom_zone']
        )
        return employees
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Backup Delivery Partner Error")
        frappe.throw(_("Error fetching delivery partners"))