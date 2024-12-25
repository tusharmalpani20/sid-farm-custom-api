import frappe
from frappe.utils import now_datetime, get_url_to_report
import pandas as pd
from io import BytesIO

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

        # Create DataFrame
        df = pd.DataFrame(data)

        # Create Excel file in memory
        excel_buffer = BytesIO()
        
        # Write to Excel with formatting
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Attendance Report', index=False)
            
            # Get workbook and worksheet objects for formatting
            workbook = writer.book
            worksheet = writer.sheets['Attendance Report']
            
            # Add formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#F8F9FA',
                'border': 1,
                'border_color': '#DFE2E5'
            })
            
            cell_format = workbook.add_format({
                'border': 1,
                'border_color': '#DFE2E5'
            })
            
            # Apply header format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Apply cell format to data
            for row_num in range(len(df)):
                for col_num in range(len(df.columns)):
                    worksheet.write(row_num + 1, col_num, df.iloc[row_num, col_num], cell_format)
            
            # Auto-adjust columns width
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(str(col))
                )
                worksheet.set_column(idx, idx, max_length + 2)

        # Get the Excel file content
        excel_content = excel_buffer.getvalue()

        # Prepare email content
        report_url = get_url_to_report('Point Wise Attendance', 'Script Report', filters)
        
        message = f"""
        <p>Dear Team,</p>
        <p>Please find attached today's Point Wise Attendance Report.</p>
        <p>You can also view the report online at: <a href="{report_url}">{report_url}</a></p>
        <br>
        <p>This is an automated message.</p>
        """

        # Send email with Excel attachment
        frappe.sendmail(
            recipients=recipients,
            subject=f"Point Wise Attendance Report - {today}",
            message=message,
            attachments=[{
                'fname': f'Point_Wise_Attendance_{today}.xlsx',
                'fcontent': excel_content
            }]
        )

        frappe.logger().info(f"Point Wise Attendance Report sent successfully for {today}")

    except Exception as e:
        frappe.logger().error(f"Failed to send Point Wise Attendance Report: {str(e)}")
        frappe.log_error(f"Point Wise Attendance Report Error: {str(e)}")
