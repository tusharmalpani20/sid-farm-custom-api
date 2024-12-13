import frappe

def after_save(doc, method):

    if doc.custom_is_notice_period:
        # Create a new Employee Separation document
        separation_doc = frappe.get_doc({
            'doctype': 'Employee Separation',
            'employee': doc.name,
            'company': doc.company,
            'boarding_begins_on': frappe.utils.nowdate(),  # Use current date
        })

        # Insert the new document
        separation_doc.insert()

        # Submit the new document
        separation_doc.submit()


        # Optionally, you can log or notify about the creation
        # frappe.msgprint(f"Employee Separation created and submitted for {doc.employee_name}")
        frappe.msgprint("A new Employee Separation document has been created.")  # New msgprint line
