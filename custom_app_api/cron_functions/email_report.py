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

        # Extract columns and data properly
        if isinstance(result, tuple):
            columns = result[0]
            data = result[1]
        else:
            columns = report.get_columns()
            data = result

        # Debug log to check data
        frappe.logger().debug(f"Report Data: {data}")
        frappe.logger().debug(f"Report Columns: {columns}")

        # Prepare HTML for PDF
        html = frappe.render_template(
            "templates/print_formats/standard.html",
            {
                "title": "Point Wise Attendance",
                "print_heading": f"Point Wise Attendance Report - {today}",
                "filters": {
                    "Date": today,
                    "Company": "SIDS FARM PRIVATE LIMITED",
                    "Include Company Descendants": "✓"
                },
                "columns": columns,
                "data": data,
                "no_letterhead": 1,
                "print_format_builder": 0,
                "align_labels_right": 0,
                "css": """
                    .print-format {
                        padding: 20px;
                        font-size: 12px;
                    }
                    .print-format table {
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                    }
                    .print-format th {
                        background-color: #f8f9fa;
                        font-weight: bold;
                        padding: 8px;
                        border: 1px solid #dfe2e5;
                        text-align: left;
                    }
                    .print-format td {
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
                        font-size: 18px;
                        font-weight: bold;
                        margin-bottom: 10px;
                    }
                """,
                "print_style": True
            }
        )

        # For debugging - save HTML to a file
        with open('/tmp/report.html', 'w') as f:
            f.write(html)

        # Generate PDF with landscape orientation and specific page size
        pdf_data = get_pdf(html, {
            'orientation': 'Landscape',
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm'
        })

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
