import frappe
from frappe.email.doctype.auto_email_report.auto_email_report import send_now
from datetime import datetime
import pytz

def send_custom_time_reports():
    """Check and send reports scheduled for the current hour"""
    
    # Get current time in system timezone (IST)
    time_zone = pytz.timezone(frappe.utils.get_system_timezone())
    current_datetime = datetime.now(time_zone)
    current_time = current_datetime.strftime("%I %p").lstrip("0")  # lstrip("0") removes leading zero
    
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
            send_now(report.name)
        except Exception as e:
            frappe.log_error(
                f"Failed to send {report.name} Auto Email Report\nError: {str(e)}",
                "Auto Email Report Error"
            )