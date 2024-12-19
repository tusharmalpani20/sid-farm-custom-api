import frappe
from frappe.utils import now_datetime

def check_routes_for_vacancies():
    try:
        print("Starting route vacancy check...")
        info_logs = []
        
        # Get all routes excluding ones with 'default' in their name (case insensitive)
        routes = frappe.get_all(
            "Route",
            filters=[
                ["route_name", "NOT LIKE", "%default%"],
                ["route_name", "NOT LIKE", "%DEFAULT%"]
            ],
            fields=["name", "branch"]
        )
        
        info_logs.append(f"Found {len(routes)} routes to check")
        print(f"Found {len(routes)} routes to check")
        
        job_openings_created = 0
        for route in routes:
            try:
                # Check if route has any active L5 grade employee
                active_l5_employees = frappe.get_all(
                    "Employee",
                    filters={
                        "status": "Active",
                        "custom_route": route.name,
                        "grade": "L5"
                    }
                )

                if not active_l5_employees:
                    info_logs.append(f"No active L5 employee found for route: {route.name}")
                    
                    # Check if job opening already exists for this route
                    existing_opening = frappe.get_all(
                        "Job Opening",
                        filters={
                            "custom_travel_route": route.name,
                            "status": "Open"
                        }
                    )

                    if existing_opening:
                        info_logs.append(f"Job opening already exists for route: {route.name}")
                        continue

                    # Get designation from previous employee if exists
                    previous_employee = frappe.get_all(
                        "Employee",
                        filters={
                            "custom_route": route.name,
                            "status": "Left"
                        },
                        fields=["designation", "name"],
                        order_by="modified DESC",
                        limit=1
                    )

                    designation = (
                        previous_employee[0].designation 
                        if previous_employee 
                        else "Delivery Partner"
                    )
                    
                    if previous_employee:
                        info_logs.append(f"Using designation '{designation}' from previous employee {previous_employee[0].name}")
                    else:
                        info_logs.append(f"No previous employee found, using default designation 'Delivery Partner'")

                    # Create job opening
                    job_opening = frappe.get_doc({
                        "doctype": "Job Opening",
                        "job_title": f"Vacancy for {route.name}",
                        "designation": designation,
                        "status": "Open",
                        "posted_on": now_datetime(),
                        "company": "SIDS FARM PRIVATE LIMITED",
                        "custom_travel_route": route.name,
                        "location": route.branch
                    })

                    job_opening.insert(ignore_permissions=True)
                    frappe.db.commit()
                    
                    job_openings_created += 1
                    info_logs.append(f"Created job opening for route: {route.name}")
                    print(f"Created job opening for route: {route.name}")

            except Exception as route_error:
                error_msg = f"Error processing route {route.name}: {str(route_error)}"
                info_logs.append(error_msg)
                frappe.log_error(
                    message=f"Error processing route: {frappe.get_traceback()}",
                    title=f"Route Processing Error - {route.name}"
                )

        # Log summary
        summary = f"""
Route Vacancy Check Summary:
Total routes checked: {len(routes)}
Job openings created: {job_openings_created}
Timestamp: {now_datetime()}
        """
        info_logs.append(summary)
        print(summary)

        # Create an info log with all information
        frappe.log_error(
            message="\n".join(info_logs),
            title="Route Vacancy Check Info Log"
        )

    except Exception as e:
        error_msg = f"Major error in route vacancy check: {str(e)}"
        print(error_msg)
        frappe.log_error(
            message=f"Error in route vacancy check:\n{frappe.get_traceback()}\nPartial Info Log:\n{chr(10).join(info_logs)}",
            title="Route Vacancy Check Error"
        )
