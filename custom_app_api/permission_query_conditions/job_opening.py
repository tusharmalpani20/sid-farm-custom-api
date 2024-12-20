import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions for Job Opening doctype based on employee's route access:
    - System Manager/Administrator: No restrictions
    - Last Mile Head/Zonal Head/Lead: Access to job openings based on their assigned routes
    Returns: string - SQL condition
    """
    
    # Skip for System Manager or Administrator
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return ""
    
    # Get the routes accessible to the user
    route_condition = frappe.get_attr("custom_app_api.custom_app_api.permission_query_conditions.Route.get_permission_query_conditions")(user)
    
    if route_condition == "1=1" or not route_condition:
        return ""
    
    # Replace table name from Route to Job Opening and field reference
    job_condition = route_condition.replace("`tabRoute`.", "`tabJob Opening`.custom_travel_")
    
    return job_condition
