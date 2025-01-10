import frappe
from frappe.utils import now_datetime, today

def before_save(doc, method):
    """Track workflow state changes for Additional Salary"""
    old_doc = doc.get_doc_before_save()
    if not old_doc:
        return

    if (doc.workflow_state in ["Submitted", "Approved", "Rejected"] and 
        doc.workflow_state != old_doc.workflow_state):
        doc.custom_workflow_action_taken_on = now_datetime()
