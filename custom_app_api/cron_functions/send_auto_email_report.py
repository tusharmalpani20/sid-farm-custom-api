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
    
    frappe.log_error(
        f"Checking reports for time: {current_time}\n"
        f"Timezone: {time_zone}\n"
        f"Full datetime: {current_datetime}",
        "Auto Email Report Debug"
    )
    
    # Get all enabled reports scheduled for current time
    enabled_reports = frappe.get_all(
        "Auto Email Report",
        filters={
            "enabled": 1,
            "frequency": "Daily at Custom Time",
            "custom_time": current_time
        },
        fields=["name", "report", "custom_time", "email_to"]
    )
    
    frappe.log_error(f"Found reports: {enabled_reports}", "Auto Email Report Debug")
    
    if not enabled_reports:
        frappe.log_error("No enabled reports found for current time", "Auto Email Report Debug")
        return

    for report in enabled_reports:
        try:
            frappe.log_error(f"Attempting to send report: {report.name}", "Auto Email Report Debug")
            send_now(report.name)
            frappe.log_error(f"Successfully sent report: {report.name}", "Auto Email Report Debug")
        except Exception as e:
            frappe.log_error(
                f"Failed to send {report.name} Auto Email Report. Error: {str(e)}\n"
                f"Report details: {report}",
                "Auto Email Report Error"
            )