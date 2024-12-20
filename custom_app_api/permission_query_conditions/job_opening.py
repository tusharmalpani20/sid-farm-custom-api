import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions for Job Opening doctype based on employee's route access:
    - System Manager/Administrator: No restrictions
    - Last Mile Head/Zonal Head/Lead: Access to job openings based on their assigned routes
    Returns: string - SQL condition
    """
    
    try:
        frappe.msgprint(f"Checking Job Opening permissions for user: {user}")
        frappe.log_error(f"Checking Job Opening permissions for user: {user}", "Job Opening Permission Check")
        
        # Skip for System Manager or Administrator
        if "System Manager" in frappe.get_roles(user) or user == "Administrator":
            frappe.log_error("User is System Manager or Administrator - No restrictions", "Job Opening Permission Check")
            return ""
        
        # Get the routes accessible to the user
        frappe.log_error("Fetching Route conditions...", "Job Opening Permission Check")
        route_condition = frappe.get_attr("custom_app_api.custom_app_api.permission_query_conditions.Route.get_permission_query_conditions")(user)
        
        frappe.log_error(f"Route condition received: {route_condition}", "Job Opening Permission Check")
        
        if route_condition == "1=1" or not route_condition:
            frappe.log_error("No specific Route conditions - Using default permissions", "Job Opening Permission Check")
            return ""
        
        # Create condition to join Job Opening with Route
        condition = f"""exists (
            select name from `tabRoute` 
            where name = `tabJob Opening`.custom_travel_route 
            and {route_condition}
        )"""
        
        frappe.log_error(f"Final Job Opening condition: {condition}", "Job Opening Permission Check")
        
        return condition
        
    except Exception as e:
        frappe.log_error(
            message=f"Error in Job Opening permissions:\n{frappe.get_traceback()}",
            title="Job Opening Permission Error"
        )
        return ""
