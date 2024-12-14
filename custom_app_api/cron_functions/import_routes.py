import frappe
import requests
from datetime import datetime

def import_routes():
    """
    Daily cron job to import routes from analytics API.
    Runs at the end of each day.
    """
    try:
        frappe.logger().info(f"Starting route import at {datetime.now()}")
        
        # Fetch data from API
        api_url = frappe.conf.get('analytics_api_url_for_routes')
        api_key = frappe.conf.get('analytics_api_key')
        
        if not api_url or not api_key:
            frappe.throw("Analytics API configuration missing in site config")
        
        frappe.logger().info("Fetching data from analytics API...")
        response = requests.get(api_url, params={"api_key": api_key})
        
        if response.status_code != 200:
            frappe.throw(f"API request failed with status code: {response.status_code}")
        
        data = response.json()
        rows = data["query_result"]["data"]["rows"]
        frappe.logger().info(f"Retrieved {len(rows)} routes from API")

        # Get existing routes map
        existing_routes = {}
        routes = frappe.get_all("Route", fields=["name", "route_name", "branch"])
        for route in routes:
            existing_routes[route.route_name] = route.name
        
        frappe.logger().info(f"Found {len(existing_routes)} existing routes in system")

        # Process each row
        new_routes_count = 0
        skipped_points_count = 0
        missing_points = set()  # To track unique missing points
        
        for row in rows:
            try:
                # Get point details first (we need branch info from here)
                point_filters = {
                    "point_name": row["delivery_point"],
                    "city_name": row["city"]
                }
                
                # First check if point exists
                if not frappe.db.exists("Point", point_filters):
                    skipped_points_count += 1
                    missing_points.add(f"{row['delivery_point']} - {row['city']}")
                    frappe.logger().warning(
                        f"Point not found: {row['delivery_point']} in {row['city']}"
                    )
                    continue
                
                point = frappe.get_doc("Point", point_filters)

                # Create route key to check existence
                route_key = f"{row['route']}-{point.branch}"
                
                # If route doesn't exist, create it
                if route_key not in existing_routes:
                    try:
                        new_route = frappe.get_doc({
                            "doctype": "Route",
                            "route_name": row["route"],
                            "point_name": point.name,
                            "area_name": point.area_name,
                            "zone_name": point.zone_name,
                            "city_name": point.city_name,
                            "state_name": point.state_name,
                            "branch": point.branch,
                            "total_delivery": 0
                        })
                        new_route.insert()
                        frappe.db.commit()
                        
                        # Add to existing routes map
                        existing_routes[route_key] = new_route.name
                        new_routes_count += 1
                        
                    except Exception as e:
                        frappe.logger().error(f"Error creating route {route_key}: {str(e)}")
                        frappe.log_error(title="Route Import Error", message=f"Error creating route {route_key}: {str(e)}")

            except Exception as e:
                frappe.logger().error(f"Error processing row {row}: {str(e)}")
                continue

        # Log summary
        summary = f"""
Route import completed:
- Total routes processed: {len(rows)}
- New routes created: {new_routes_count}
- Points not found (skipped): {skipped_points_count}
- Missing Points: {', '.join(missing_points)}
- Timestamp: {datetime.now()}
"""
        frappe.logger().info(summary)
        
        # If there were missing points, create an error log
        if missing_points:
            frappe.log_error(
                title="Route Import - Missing Points",
                message=f"The following points were missing:\n{', '.join(missing_points)}"
            )

    except Exception as e:
        error_msg = f"Route import failed: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error(title="Route Import Failed", message=error_msg)
        raise
