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
    today = current_datetime.strftime("%Y-%m-%d")
    
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
            doc = frappe.get_doc("Auto Email Report", report.name)
            
            # Update date only for Point Wise Attendance report
            if doc.report == "Point Wise Attendance":
                filters = frappe.parse_json(doc.filters)
                if "date" in filters:
                    filters["date"] = current_datetime.strftime("%d-%m-%Y")
                    doc.filters = frappe.as_json(filters)
                    doc.save()
            # Update from and to dates for Delivery Partner Status Report
            elif doc.report == "Delivery Partner Status Report":
                filters = frappe.parse_json(doc.filters)
                if "from" in filters and "to" in filters:
                    # Get yesterday's date
                    yesterday = (current_datetime - frappe.utils.datetime.timedelta(days=1)).strftime("%d-%m-%Y")
                    filters["from"] = yesterday
                    filters["to"] = current_datetime.strftime("%d-%m-%Y")
                    doc.filters = frappe.as_json(filters)
                    doc.save()
            
            send_now(report.name)
        except Exception as e:
            frappe.log_error(
                f"Failed to send {report.name} Auto Email Report\nError: {str(e)}",
                "Auto Email Report Error"
            )