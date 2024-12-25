import frappe
from frappe.utils import now_datetime, get_url_to_report
from frappe.utils.pdf import get_pdf

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

        # Prepare HTML for PDF using Frappe's standard report print format
        html = frappe.render_template(
            "templates/print_formats/standard.html",
            {
                "title": "Point Wise Attendance",
                "print_heading": f"Point Wise Attendance Report - {today}",
                "filters": {
                    "Date": today,
                    "Points": "",
                    "Company": "SIDS FARM PRIVATE LIMITED",
                    "Include Company Descendants": "✓"
                },
                "columns": report.get_columns(),
                "data": result[1] if isinstance(result, tuple) else result,
                "report": report,
                "letter_head": frappe.get_doc("Letter Head", "Standard"),
                "no_letterhead": 1,
                "css": """
                    .print-format {
                        padding: 20px;
                    }
                    .print-format table {
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                    }
                    .print-format th {
                        background-color: #f8f9fa;
                        font-weight: bold;
                    }
                    .print-format th, .print-format td {
                        padding: 8px;
                        border: 1px solid #dfe2e5;
                        text-align: left;
                    }
                    .print-format tr:nth-child(even) {
                        background-color: #f8f9fa;
                    }
                    .print-format tr:last-child {
                        font-weight: bold;
                        background-color: #f8f9fa;
                    }
                    .filter-section {
                        margin-bottom: 20px;
                    }
                    .report-title {
                        font-size: 20px;
                        font-weight: bold;
                        margin-bottom: 10px;
                    }
                """
            }
        )

        # Generate PDF
        pdf_data = get_pdf(html, {'orientation': 'Landscape'})

        # Prepare email content
        report_url = get_url_to_report('Point Wise Attendance', 'Script Report', filters)
        
        message = f"""
        <p>Dear Team,</p>
        <p>Please find attached today's Point Wise Attendance Report.</p>
        <p>You can also view the report online at: <a href="{report_url}">{report_url}</a></p>
        <br>
        <p>This is an automated message.</p>
        """

        # Send email with PDF attachment
        frappe.sendmail(
            recipients=recipients,
            subject=f"Point Wise Attendance Report - {today}",
            message=message,
            attachments=[{
                'fname': f'Point_Wise_Attendance_{today}.pdf',
                'fcontent': pdf_data
            }]
        )

        frappe.logger().info(f"Point Wise Attendance Report sent successfully for {today}")

    except Exception as e:
        frappe.logger().error(f"Failed to send Point Wise Attendance Report: {str(e)}")
        frappe.log_error(f"Point Wise Attendance Report Error: {str(e)}")
