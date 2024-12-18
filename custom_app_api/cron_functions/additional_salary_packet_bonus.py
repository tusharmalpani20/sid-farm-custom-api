import frappe
import requests
from datetime import datetime, date
from calendar import monthrange
from frappe.utils import getdate, add_months, get_first_day, get_last_day

def calculate_packet_bonus():
    """
    Monthly cron job to calculate and distribute packet bonus among delivery partners.
    Runs at the end of each month.
    """
    try:
        current_date = getdate()
        # Get last month's date range since we're calculating for previous month
        first_day = get_first_day(add_months(current_date, -1))
        last_day = get_last_day(first_day)
        
        frappe.logger().info(f"Starting packet bonus calculation for period: {first_day} to {last_day}")
        
        # Fetch data from API
        api_url = frappe.conf.get('analytics_api_url_for_packet_bonus')
        api_key = frappe.conf.get('analytics_api_key_for_packet_bonus')
        
        if not api_url or not api_key:
            frappe.throw("Analytics API configuration missing in site config")
        
        # Get API data
        response = requests.get(api_url, params={"api_key": api_key})
        if response.status_code != 200:
            frappe.throw(f"API request failed with status code: {response.status_code}")
        
        data = response.json()
        bonus_rows = data["query_result"]["data"]["rows"]
        
        # Create API data map (route_name + city as key)
        api_bonus_map = {}
        for row in bonus_rows:
            if row["bonus amount"] <= 0:  # Using correct key name with space
                continue
            key = f"{row['Route name']}_{row['city_cd']}"  # Using city_cd instead of city
            api_bonus_map[key] = {
                "bonus_amount": row["bonus amount"],
                "warehouse": row["warehouse"],
                "zone": row["zone"],
                "area": row["area"]
            }

        # Get all routes from system
        routes = frappe.get_all("Route", 
            fields=["name", "route_name", "city_name", "branch"]
        )

        # Create route maps
        route_name_map = {}  # System generated name as key
        route_composite_map = {}  # route_name + city as key
        
        for route in routes:
            route_name_map[route.name] = route
            key = f"{route.route_name}_{route.city_name}"
            route_composite_map[key] = route

        # Process bonus calculation
        processed_routes = 0
        bonus_entries_created = 0
        errors = []

        # Define eligible designations
        ELIGIBLE_DESIGNATIONS = [
            "Delivery Partner",
            "Backup Delivery Partner",
            "Extra Delivery Partner",
            "Agent Delivery Partner"
        ]

        for composite_key, route_data in route_composite_map.items():
            try:
                if composite_key not in api_bonus_map:
                    continue

                bonus_info = api_bonus_map[composite_key]
                total_bonus = bonus_info["bonus_amount"]

                # Get attendance records for this route with designation filter
                attendance_records = frappe.get_all(
                    "Attendance",
                    filters={
                        "custom_route": route_data.name,
                        "attendance_date": ["between", [first_day, last_day]],
                        "status": "Present",
                        "docstatus": 1
                    },
                    fields=["employee", "attendance_date"]
                )

                # Create employee attendance map
                employee_days = {}
                date_employee_map = {}  # To track multiple punches on same day
                ineligible_employees = set()  # Track employees with wrong designation

                for record in attendance_records:
                    # Check employee designation first
                    employee_doc = frappe.get_doc("Employee", record.employee)
                    
                    if employee_doc.designation not in ELIGIBLE_DESIGNATIONS:
                        ineligible_employees.add(f"{employee_doc.employee_name} ({employee_doc.designation})")
                        continue

                    date_str = record.attendance_date.strftime('%Y-%m-%d')
                    
                    # Check for multiple punches on same day
                    if date_str in date_employee_map:
                        frappe.logger().warning(
                            f"Multiple attendance found for date {date_str} on route {route_data.name}"
                        )
                        continue
                    
                    date_employee_map[date_str] = record.employee
                    employee_days[record.employee] = employee_days.get(record.employee, 0) + 1

                # Log ineligible employees if any
                if ineligible_employees:
                    frappe.logger().warning(
                        f"Skipped ineligible employees for route {route_data.route_name}: "
                        f"{', '.join(ineligible_employees)}"
                    )

                # Calculate and create bonus entries
                if employee_days:
                    total_days = sum(employee_days.values())
                    
                    # Create a summary of attendance for the reason field
                    employee_details = []
                    for employee, days in employee_days.items():
                        emp_doc = frappe.get_doc("Employee", employee)
                        employee_details.append(
                            f"{emp_doc.employee_name} ({emp_doc.designation}): {days} days"
                        )

                    # Format the reason with detailed information
                    reason = f"""Packet Bonus for {first_day.strftime('%B %Y')}
Route: {route_data.route_name}
City: {route_data.city_name}
Zone: {bonus_info['zone']}
Area: {bonus_info['area']}
Total Bonus Amount: ₹{total_bonus:,.2f}
Total Working Days: {total_days}
Employee Distribution:
{chr(10).join(employee_details)}"""

                    if ineligible_employees:
                        reason += f"\n\nIneligible Employees (Skipped):\n{chr(10).join(ineligible_employees)}"

                    for employee, days in employee_days.items():
                        # Calculate proportional bonus
                        employee_bonus = (days / total_days) * total_bonus
                        emp_doc = frappe.get_doc("Employee", employee)

                        if employee_bonus > 0:
                            # Create Additional Salary entry with detailed reason
                            additional_salary = frappe.get_doc({
                                "doctype": "Additional Salary",
                                "employee": employee,
                                "employee_name": emp_doc.employee_name,
                                "salary_component": "Packet Bonus",
                                "amount": employee_bonus,
                                "payroll_date": last_day,
                                "company": emp_doc.company,
                                "custom_route": route_data.name,
                                "custom_attendance_days": days,
                                "custom_reason": reason,
                                "overwrite_salary_structure_amount": 1,
                                "workflow_state": "Submitted"  # Set the workflow state
                            })
                            additional_salary.flags.ignore_permissions = True
                            additional_salary.flags.ignore_workflow = True  # Skip workflow validation
                            additional_salary.insert()
                            additional_salary.submit()
                            bonus_entries_created += 1

                            frappe.logger().info(
                                f"Created bonus entry for {emp_doc.employee_name} "
                                f"({emp_doc.designation}) - ₹{employee_bonus:,.2f} "
                                f"for {days}/{total_days} days"
                            )

                processed_routes += 1

            except Exception as e:
                error_msg = f"Error processing route {composite_key}: {str(e)}"
                errors.append(error_msg)
                frappe.logger().error(error_msg)
                continue

        # Commit all changes
        frappe.db.commit()

        # Log summary
        summary = f"""
Packet Bonus Calculation completed for {first_day} to {last_day}:
- Total routes processed: {processed_routes}
- Bonus entries created: {bonus_entries_created}
- Errors encountered: {len(errors)}
- Timestamp: {datetime.now()}
"""
        frappe.logger().info(summary)

        # If there were errors, create an error log
        if errors:
            frappe.log_error(
                title=f"Packet Bonus Calculation Errors - {first_day}",
                message="\n".join(errors)
            )

    except Exception as e:
        error_msg = f"Packet bonus calculation failed: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error(title="Packet Bonus Calculation Failed", message=error_msg)
        raise
