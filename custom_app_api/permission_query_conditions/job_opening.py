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
    
    #if the user role is PAN India Access - Data then aslo we will show the data for all the employees
    if "PAN India Access - Data" in frappe.get_roles(user):
        return ""
    
    #if the user role is Read Only then aslo we will show the data for all the employees
    if "Read Only" in frappe.get_roles(user):
        return " and ".join(conditions)
    
    # Get the routes accessible to the user
    route_condition = frappe.get_attr("custom_app_api.permission_query_conditions.Route.get_permission_query_conditions")(user)
    
    if route_condition == "1=1" or not route_condition:
        return ""
    
    # Create condition to join Job Opening with Route
    condition = f"""exists (
        select name from `tabRoute` 
        where name = `tabJob Opening`.custom_travel_route 
        and {route_condition}
    )"""
    
    return condition
