import frappe
from frappe.utils import now_datetime, get_url_to_report
import csv
from io import StringIO

def send_point_wise_attendance_report():
    """Send Point Wise Attendance report daily at 10 PM"""
    try:
        # Get today's date in YYYY-MM-DD format
        today = now_datetime().date()

        # Create report filters
        filters = {
            "date": today,
            "company": "SIDS FARM PRIVATE LIMITED",
            "include_company_descendants": 1
        }

        # Get recipients from site_config.json
        recipients = frappe.conf.get('attendance_report_recipients', [])
        
        if not recipients:
            frappe.logger().error("No recipients configured in site_config.json for attendance report")
            return

        # Generate report content
        report = frappe.get_doc('Report', 'Point Wise Attendance')
        result = report.get_data(filters=filters, as_dict=True)

        # Extract columns and data
        if isinstance(result, tuple):
            columns = result[0]
            data = result[1]
        else:
            columns = report.get_columns()
            data = result

        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)

        # Write headers
        headers = [col.get('label') for col in columns]
        writer.writerow(headers)

        # Write data rows
        for row in data:
            writer.writerow([row.get(col.get('fieldname')) for col in columns])

        # Get CSV content
        csv_content = output.getvalue()

        # Prepare email content
        report_url = get_url_to_report('Point Wise Attendance', 'Script Report', filters)
        
        message = f"""
        <p>Dear Team,</p>
        <p>Please find attached today's Point Wise Attendance Report.</p>
        <p>You can also view the report online at: <a href="{report_url}">{report_url}</a></p>
        <br>
        <p>This is an automated message.</p>
        """

        # Send email with CSV attachment
        frappe.sendmail(
            recipients=recipients,
            subject=f"Point Wise Attendance Report - {today}",
            message=message,
            attachments=[{
                'fname': f'Point_Wise_Attendance_{today}.csv',
                'fcontent': csv_content
            }]
        )

        frappe.logger().info(f"Point Wise Attendance Report sent successfully for {today}")

    except Exception as e:
        frappe.logger().error(f"Failed to send Point Wise Attendance Report: {str(e)}")
        frappe.log_error(f"Point Wise Attendance Report Error: {str(e)}")
