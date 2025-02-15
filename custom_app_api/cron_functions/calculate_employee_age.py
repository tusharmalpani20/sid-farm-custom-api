from datetime import datetime
from frappe.model.document import Document
import frappe

def calculate_employee_age():
    # Get all employees with date_of_birth field
    employees = frappe.get_all("Employee", 
                             filters={"date_of_birth": ["is", "set"]},
                             fields=["name", "date_of_birth", "custom_age"])
    
    today = datetime.now().date()
    
    for employee in employees:
        # Calculate age
        dob = employee.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        
        # Only update if age is positive and different from current custom_age
        if age >= 0 and age != employee.custom_age:
            frappe.db.set_value("Employee", employee.name, "custom_age", age)
    
    frappe.db.commit()
