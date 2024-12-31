import frappe
from frappe.model.document import Document
from frappe import _
import time

class BackupDeliveryPartnerMapping(Document):
    @frappe.whitelist()
    def get_backup_delivery_partners(self):
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
            
        employees = frappe.get_all(
            "Employee",
            filters=filters,
            fields=["name", "employee_name", "custom_route", "custom_point", 
                   "custom_area", "custom_zone"]
        )
        
        return employees

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
            doc.custom_route = route
            # doc.custom_point = point
            # doc.custom_area = area
            # doc.custom_zone = zone
            doc.save(ignore_permissions=False)
            
            return {
                "message": "Employee details updated successfully",
                "status": "success"
            }
        
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
        employees = frappe.get_all('Employee',
            filters={
                'designation': 'Backup Delivery Partner',
                'status': 'Active'
            },
            fields=['name', 'employee_name', 'custom_route', 'custom_point', 'custom_area', 'custom_zone']
        )
        return employees
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Backup Delivery Partner Error")
        frappe.throw(_("Error fetching delivery partners"))