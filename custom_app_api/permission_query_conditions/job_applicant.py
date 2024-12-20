import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions for Job Applicant doctype based on employee's route access:
    - System Manager/Administrator: No restrictions
    - Last Mile Head/Zonal Head/Lead: Access to job applicants based on their assigned routes via Job Opening
    Returns: string - SQL condition
    """
    
    frappe.msgprint(f"Checking Job Applicant permissions for user: {user}")
    
    # Skip for System Manager or Administrator
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        frappe.msgprint("User is System Manager or Administrator - No restrictions")
        return ""
    
    # Get the routes accessible to the user
    frappe.msgprint("Fetching Route conditions...")
    route_condition = frappe.get_attr("custom_app_api.custom_app_api.permission_query_conditions.Route.get_permission_query_conditions")(user)
    
    frappe.msgprint(f"Route condition received: {route_condition}")
    
    if route_condition == "1=1" or not route_condition:
        frappe.msgprint("No specific Route conditions - Using default permissions")
        return ""
    
    # Create nested condition to join Job Applicant with Job Opening and Route
    condition = f"""exists (
        select jo.name 
        from `tabJob Opening` jo
        inner join `tabRoute` r on r.name = jo.custom_travel_route
        where jo.name = `tabJob Applicant`.job_title 
        and {route_condition.replace('`tabRoute`', 'r')}
    )"""
    
    frappe.msgprint(f"Final Job Applicant condition: {condition}")
    
    return condition
