import frappe
from frappe.utils import now_datetime, get_url_to_report
import csv
from io import StringIO
from frappe.utils.pdf import get_pdf

# HTML template as a string variable
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        .report-table { 
            width: 100%; 
            border-collapse: collapse; 
            margin-top: 20px;
        }
        .report-table th, .report-table td { 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: left; 
        }
        .report-table th { 
            background-color: #f5f5f5; 
            font-weight: bold; 
        }
        .report-table tr:nth-child(even) { 
            background-color: #f9f9f9; 
        }
        .report-table tr:last-child { 
            font-weight: bold; 
            background-color: #f5f5f5; 
        }
        .report-header {
            margin-bottom: 20px;
        }
        .report-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .report-date {
            color: #666;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="report-header">
        <div class="report-title">{{ title }}</div>
        <div class="report-date">Date: {{ date }}</div>
    </div>
    
    <table class="report-table">
        <thead>
            <tr>
                {% for col in columns %}
                <th>{{ col.label }}</th>
                {% endfor %}
            </tr>
        </thead>
        <tbody>
            {% for row in data %}
            <tr>
                {% for col in columns %}
                <td>
                    {% if col.fieldtype == "Percent" %}
                        {{ "%.1f"|format(row[col.fieldname]|float) }}%
                    {% else %}
                        {{ row[col.fieldname] }}
                    {% endif %}
                </td>
                {% endfor %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

def generate_csv_report(columns, data):
    """Generate CSV report content"""
    output = StringIO()
    writer = csv.writer(output)

    # Write headers
    headers = [col.get('label') for col in columns]
    writer.writerow(headers)

    # Write data rows
    for row in data:
        writer.writerow([row.get(col.get('fieldname')) for col in columns])

    return output.getvalue()

def generate_excel_report(columns, data):
    """Generate Excel report content using Frappe's built-in functionality"""
    from frappe.utils.xlsxutils import make_xlsx
    
    # Prepare data for Excel
    xlsx_data = make_xlsx([{
        'data': {
            'headers': [col.get('label') for col in columns],
            'rows': [[row.get(col.get('fieldname')) for col in columns] for row in data]
        }
    }], 'Point Wise Attendance')
    
    # Get the bytes from BytesIO object
    return xlsx_data.getvalue()

def generate_pdf_report(columns, data, date):
    """Generate PDF report content with custom HTML template"""
    html = frappe.render_template(
        HTML_TEMPLATE,
        {
            "title": "Point Wise Attendance Report",
            "date": date,
            "columns": columns,
            "data": data
        }
    )
    
    return get_pdf(html, {'orientation': 'Landscape'})

def send_point_wise_attendance_report():
    """Send Point Wise Attendance report in multiple formats"""
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

        # Generate reports in different formats
        # csv_content = generate_csv_report(columns, data)
        # excel_content = generate_excel_report(columns, data)
        pdf_content = generate_pdf_report(columns, data, today)

        # Prepare email content
        report_url = get_url_to_report('Point Wise Attendance', 'Script Report', filters)
        
        message = f"""
        <p>Dear Team,</p>
        <p>Please find attached today's Point Wise Attendance Report in multiple formats:</p>
        <ul>
            <li>CSV format for easy data import</li>
            <li>Excel format for analysis and filtering</li>
            <li>PDF format for printing and sharing</li>
        </ul>
        <p>You can also view the report online at: <a href="https://sf.hopnet.co.in/app/query-report/Point%20Wise%20Attendance">{report_url}</a></p>
        <br>
        <p>This is an automated message.</p>
        """

        # Send email with all attachments
        frappe.sendmail(
            recipients=recipients,
            subject=f"Point Wise Attendance Report - {today}",
            message=message,
            attachments=[
                # {
                #     'fname': f'Point_Wise_Attendance_{today}.csv',
                #     'fcontent': csv_content
                # },
                # {
                #     'fname': f'Point_Wise_Attendance_{today}.xlsx',
                #     'fcontent': excel_content
                # },
                {
                    'fname': f'Point_Wise_Attendance_{today}.pdf',
                    'fcontent': pdf_content
                }
            ]
        )

        frappe.logger().info(f"Point Wise Attendance Report sent successfully for {today}")

    except Exception as e:
        frappe.logger().error(f"Failed to send Point Wise Attendance Report: {str(e)}")
        frappe.log_error(f"Point Wise Attendance Report Error: {str(e)}")
