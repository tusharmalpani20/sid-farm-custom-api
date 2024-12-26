import frappe
from frappe.email.doctype.auto_email_report.auto_email_report import AutoEmailReport
from datetime import datetime

def send_custom_time_reports():
    """Check and send reports scheduled for the current hour"""
    
    # Get current time in 12-hour format (e.g., "10 AM", "2 PM")
    current_time = datetime.now().strftime("%I %p").lstrip("0")  # lstrip("0") removes leading zero
    
    # Get all enabled reports scheduled for current time
    enabled_reports = frappe.get_all(
        "Auto Email Report",
        filters={
            "enabled": 1,
            "frequency": "Daily at Custom Time",
            "custom_time": current_time
        }
    )

    for report in enabled_reports:
        try:
            auto_email_report = frappe.get_doc("Auto Email Report", report.name)
            auto_email_report.send()
        except Exception:
            auto_email_report.log_error(f"Failed to send {auto_email_report.name} Auto Email Report")