import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions for Route doctype based on employee hierarchy and geographical assignments:
    - System Manager/Administrator: No restrictions
    - Last Mile Head: Access to routes in their branch
    - Last Mile Zonal Head: Access to routes in their zone
    - Last Mile Lead: Access to routes in their area
    Returns: string - SQL condition
    """
    
    conditions = []
    
    # Skip for System Manager or Administrator
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return " and ".join(conditions)
    
    # Get employee record for logged-in user
    employee = frappe.db.get_value("Employee", 
        {"user_id": user}, 
        ["name", "designation", "branch", "custom_zone", "custom_area", "custom_point"],
        as_dict=1
    )
    
    if not employee:
        return " and ".join(conditions)  # Return default permissions if no employee record
    
    # Apply filters based on designation
    if employee.designation == "Last Mile Head":
        if employee.branch:
            conditions.append(f"branch = '{employee.branch}'")
            
    elif employee.designation == "Last Mile Zonal Head":
        if employee.custom_zone:
            conditions.append(f"zone_name = '{employee.custom_zone}'")
            
    elif employee.designation == "Last Mile Lead":
        if employee.custom_area:
            conditions.append(f"area_name = '{employee.custom_area}'")
    
    final_condition = " and ".join(conditions)
    return final_condition
