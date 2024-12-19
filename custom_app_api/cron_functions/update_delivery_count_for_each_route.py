import frappe
import requests
from datetime import datetime

def update_delivery_count_for_routes():
    """
    Daily cron job to update delivery counts for routes from analytics API.
    Runs at 11 PM each day.
    """
    try:
        frappe.logger().info(f"Starting delivery count update at {datetime.now()}")
        
        # Fetch data from API
        api_url = frappe.conf.get('analytics_api_url_for_delivery_counts')
        api_key = frappe.conf.get('analytics_api_key')
        
        if not api_url or not api_key:
            frappe.throw("Analytics API configuration missing in site config")
        
        frappe.logger().info("Fetching delivery count data from analytics API...")
        response = requests.get(api_url, params={"api_key": api_key})
        
        if response.status_code != 200:
            frappe.throw(f"API request failed with status code: {response.status_code}")
        
        data = response.json()
        rows = data["query_result"]["data"]["rows"]
        frappe.logger().info(f"Retrieved {len(rows)} delivery counts from API")

        # Get existing routes map
        existing_routes = {}
        routes = frappe.get_all("Route", fields=["name", "route_name", "city_name"])
        for route in routes:
            route_key = f"{route.route_name}-{route.city_name}"
            existing_routes[route_key] = route.name
        
        frappe.logger().info(f"Found {len(existing_routes)} existing routes in system")

        # Process each row
        updated_routes_count = 0
        skipped_routes_count = 0
        missing_routes = set()  # To track unique missing routes
        
        for row in rows:
            try:
                route_key = f"{row['route']}-{row['city']}"
                
                if route_key not in existing_routes:
                    skipped_routes_count += 1
                    missing_routes.add(route_key)
                    frappe.logger().warning(
                        f"Route not found: {row['route']} in {row['city']}"
                    )
                    continue
                
                # Update the route's delivery count
                route_doc = frappe.get_doc("Route", existing_routes[route_key])
                route_doc.total_delivery = row["count_of_customers"]
                route_doc.save()
                frappe.db.commit()
                updated_routes_count += 1

            except Exception as e:
                frappe.logger().error(f"Error processing row {row}: {str(e)}")
                continue

        # Log summary
        summary = f"""
Delivery count update completed:
- Total counts processed: {len(rows)}
- Routes updated: {updated_routes_count}
- Routes not found (skipped): {skipped_routes_count}
- Missing Routes: {', '.join(missing_routes)}
- Timestamp: {datetime.now()}
"""
        frappe.logger().info(summary)
        
        # If there were missing routes, create an error log
        if missing_routes:
            frappe.log_error(
                title="Delivery Count Update - Missing Routes",
                message=f"The following routes were missing:\n{', '.join(missing_routes)}"
            )

    except Exception as e:
        error_msg = f"Delivery count update failed: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error(title="Delivery Count Update Failed", message=error_msg)
        raise
