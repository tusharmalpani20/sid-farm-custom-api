import frappe
from frappe.utils import now_datetime

def on_update(doc, method):
    """Track workflow state changes for Additional Salary"""
    try:
        # Check if document is in a significant workflow state
        if doc.workflow_state in ["Submitted", "Approved", "Rejected"]:
            current_time = now_datetime()
            
            # Update timestamp using db_set with commit=True
            doc.db_set('workflow_action_taken_on', current_time, update_modified=False, commit=True)
            
            # Verify the update by reloading the document
            updated_doc = frappe.get_doc('Additional Salary', doc.name)
            # frappe.msgprint(f"⏰ Stored timestamp value: {updated_doc.custom_workflow_action_taken_on}")
    except Exception as e:
        frappe.log_error(f"Error updating timestamp: {str(e)}", "Additional Salary Update Error")
        frappe.msgprint(f"Error: {str(e)}", indicator="red")