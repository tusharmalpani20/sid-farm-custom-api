import frappe
from frappe.utils import now_datetime

def on_update(doc, method):
    """Track workflow state changes for Additional Salary"""
    
    # Debug message to confirm function trigger
    frappe.msgprint("⚡ On Update triggered for Additional Salary")
    
    # Check if document is in a significant workflow state
    if doc.workflow_state in ["Submitted", "Approved", "Rejected"]:
        # Debug message to show current state
        frappe.msgprint(f"📝 Current workflow state: {doc.workflow_state}")
        
        # Update timestamp using db_set to avoid recursive updates
        doc.db_set('custom_workflow_action_taken_on', now_datetime(), update_modified=False)
        frappe.msgprint(f"⏰ Timestamp updated to: {doc.custom_workflow_action_taken_on}")