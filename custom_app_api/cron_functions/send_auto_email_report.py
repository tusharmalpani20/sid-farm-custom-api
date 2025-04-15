from datetime import datetime, timedelta
from frappe.utils import add_to_date
import frappe
from frappe.email.doctype.auto_email_report.auto_email_report import send_now

def send_custom_time_reports():
    """Check and send reports scheduled for the current hour"""
    
    # Get current time and add 5:30 for IST
    current_datetime = datetime.now() + timedelta(hours=5, minutes=30)
    current_time = current_datetime.strftime("%I %p").lstrip("0")  # For hour format like "9 AM"
    # today = current_datetime.strftime('%d-%m-%Y')  # Format as DD-MM-YYYY
    today = current_datetime.strftime('%Y-%m-%d')  # Format as YYYY-MM-DD
    
    print(f"Current Time: {current_time}")  # Debug print
    
    # Get all enabled reports scheduled for current time
    enabled_reports = frappe.get_all(
        "Auto Email Report",
        filters={
            "enabled": 1,
            "frequency": "Daily at Custom Time",
            "custom_time": current_time  # This checks if report is scheduled for current hour (e.g., "9 AM")
        }
    )

    print(f"Found {len(enabled_reports)} reports for time {current_time}")  # Debug print

    for report in enabled_reports:
        try:
            doc = frappe.get_doc("Auto Email Report", report.name)
            print(f"Processing report: {doc.report} scheduled for {doc.custom_time}")  # Debug print
            
            # Update date only for Point Wise Attendance report
            if doc.report == "Point Wise Attendance-Hyderabad":
                filters = frappe.parse_json(doc.filters)
                filters["branch"] = ["Hyderabad"]
                if "date" in filters:
                    filters["date"] = today
                    doc.filters = frappe.as_json(filters)
                    doc.save()
                print(f"Filters updated for {doc.report}: {filters}")
                print(f"Today's date: {today}")
                
                # Check if there are any present records for today
                present_records = frappe.get_all(
                    "Attendance",
                    filters={
                        "attendance_date": today,
                        "status": "Present",
                        "custom_branch": "Hyderabad",
                        "docstatus": 1
                    }
                )
                
                if not present_records:
                    print(f"No present records found for {today}. Skipping Point Wise Attendance report.")
                    continue
            elif doc.report == "Point Wise Attendance-Bengaluru":
                filters = frappe.parse_json(doc.filters)
                filters["branch"] = ["Bengaluru"]
                if "date" in filters:
                    filters["date"] = today
                    doc.filters = frappe.as_json(filters)
                    doc.save()
                print(f"Filters updated for {doc.report}: {filters}")
                print(f"Today's date: {today}")
                
                # Check if there are any present records for today
                present_records = frappe.get_all(
                    "Attendance",
                    filters={
                        "attendance_date": today,
                        "status": "Present",
                        "custom_branch": "Bengaluru",
                        "docstatus": 1
                    }
                )
                
                if not present_records:
                    print(f"No present records found for {today}. Skipping Point Wise Attendance report.")
                    continue
                    
            elif doc.report == "Delivery Partner Status Report":
                filters = frappe.parse_json(doc.filters)
                if "from" in filters and "to" in filters:
                    yesterday = add_to_date(today, days=-1)
                    filters["from"] = yesterday
                    filters["to"] = today
                    doc.filters = frappe.as_json(filters)
                    doc.save()
            
            send_now(report.name)
        except Exception as e:
            frappe.log_error(
                f"Failed to send {report.name} Auto Email Report\nError: {str(e)}",
                "Auto Email Report Error"
            )