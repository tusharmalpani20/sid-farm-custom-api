import frappe
from frappe.utils import now_datetime
import sys

def check_routes_for_vacancies():
    try:
        print("Starting route vacancy check...", flush=True)
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
        print(f"Found {len(routes)} routes to check", flush=True)
        
        job_openings_created = 0
        for route in routes:
            try:
                # Add detailed logging for specific route
                is_target_route = route.name == "JUBILEE_HILLS_CHECKPOST_FAS-Hyderabad"
                if is_target_route:
                    info_logs.append(f"\n=== Detailed check for {route.name} ===")
                    print(f"\n=== Detailed check for {route.name} ===", flush=True)

                # Check if route has any active L5 grade employee
                active_l5_employees = frappe.get_all(
                    "Employee",
                    filters={
                        "status": "Active",
                        "custom_route": route.name,
                        "grade": "L5"
                    }
                )

                if is_target_route:
                    info_logs.append(f"Active L5 employees found: {len(active_l5_employees)}")
                    print(f"Active L5 employees found: {len(active_l5_employees)}", flush=True)
                    if active_l5_employees:
                        info_logs.append(f"Active L5 employee details: {active_l5_employees}")
                        print(f"Active L5 employee details: {active_l5_employees}", flush=True)
                    else:
                        info_logs.append("No active L5 employee found")
                        print("No active L5 employee found", flush=True)

                if not active_l5_employees:
                    if is_target_route:
                        info_logs.append("No active L5 employee found - checking for existing job opening")
                        print("No active L5 employee found - checking for existing job opening", flush=True)
                    
                    # Check if job opening already exists for this route - with broader search
                    existing_opening = frappe.get_all(
                        "Job Opening",
                        filters={
                            "custom_travel_route": route.name,
                            "status": ["in", ["Open", "Closed"]]  # Check both statuses
                        },
                        fields=["name", "status", "custom_travel_route", "route"]
                    )

                    if is_target_route:
                        print(f"Checking ALL job openings for route {route.name}:", flush=True)
                        print(f"Existing openings found: {len(existing_opening)}", flush=True)
                        if existing_opening:
                            print("Details of existing openings:", flush=True)
                            for opening in existing_opening:
                                print(f"- Name: {opening.name}, Status: {opening.status}, Route: {opening.route}", flush=True)
                        
                        # Also check for any job openings with similar route
                        similar_openings = frappe.get_all(
                            "Job Opening",
                            filters={
                                "route": "jobs/sids_farm_private_limited/delivery-partner"
                            },
                            fields=["name", "status", "custom_travel_route", "route"]
                        )
                        if similar_openings:
                            print("\nFound job openings with route 'jobs/sids_farm_private_limited/delivery-partner':", flush=True)
                            for opening in similar_openings:
                                print(f"- Name: {opening.name}, Status: {opening.status}, Custom Route: {opening.custom_travel_route}", flush=True)

                    if not existing_opening:
                        if is_target_route:
                            print("No existing job opening found - proceeding to create new one", flush=True)
                        
                        # Get designation from previous employee if exists
                        previous_employee = frappe.get_all(
                            "Employee",
                            filters={
                                "custom_route": route.name,
                                "grade": "L5",
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
                        
                        if is_target_route:
                            if previous_employee:
                                print(f"Using designation '{designation}' from previous employee {previous_employee[0].name}", flush=True)
                            else:
                                print(f"No previous employee found, using default designation 'Delivery Partner'", flush=True)

                        try:
                            # Create job opening with modified route field
                            job_opening = frappe.get_doc({
                                "doctype": "Job Opening",
                                "job_title": f"Vacancy for {route.name}",
                                "designation": designation,
                                "status": "Open",
                                "posted_on": now_datetime(),
                                "company": "SIDS FARM PRIVATE LIMITED",
                                "custom_travel_route": route.name,
                                "location": route.branch,
                                "route": f"jobs/sids_farm_private_limited/{route.name.lower()}"  # Make route unique
                            })

                            if is_target_route:
                                print(f"\nAttempting to create job opening with data:", flush=True)
                                print(f"Route: {route.name}", flush=True)
                                print(f"Branch: {route.branch}", flush=True)
                                print(f"Designation: {designation}", flush=True)
                                print(f"Route field: jobs/sids_farm_private_limited/{route.name.lower()}", flush=True)

                            job_opening.insert(ignore_permissions=True)
                            frappe.db.commit()
                            
                            job_openings_created += 1
                            if is_target_route:
                                print(f"Successfully created job opening!", flush=True)

                        except Exception as job_error:
                            if is_target_route:
                                print(f"\nFailed to create job opening: {str(job_error)}", flush=True)
                                print("Full error details:", flush=True)
                                print(frappe.get_traceback(), flush=True)
                            frappe.log_error(
                                message=f"Error creating job opening: {frappe.get_traceback()}",
                                title=f"Job Opening Creation Error - {route.name}"
                            )

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
        print(summary, flush=True)

        # Create an info log with all information
        frappe.log_error(
            message="\n".join(info_logs),
            title="Route Vacancy Check Info Log"
        )

    except Exception as e:
        error_msg = f"Major error in route vacancy check: {str(e)}"
        print(error_msg, flush=True)
        frappe.log_error(
            message=f"Error in route vacancy check:\n{frappe.get_traceback()}\nPartial Info Log:\n{chr(10).join(info_logs)}",
            title="Route Vacancy Check Error"
        )
