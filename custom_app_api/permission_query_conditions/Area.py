import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions for Area doctype based on employee hierarchy and geographical assignments:
    - System Manager/Administrator: No restrictions
    - Last Mile Head: Access to areas in their branch
    - Last Mile Zonal Head: Access to areas in their zone
    - Last Mile Lead: Access to areas in their assigned areas
    Returns: string - SQL condition
    """
    
    conditions = []
    
    # Skip for System Manager or Administrator
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return ""

    #if the user role is PAN India Access - Data then aslo we will show the data for all the employees
    if "PAN India Access - Data" in frappe.get_roles(user):
        return ""
    
    # Get employee record for logged-in user
    employee = frappe.db.get_value("Employee", 
        {"user_id": user}, 
        ["name", "designation", "branch", "custom_zone", "custom_area"],
        as_dict=1
    )
    
    if not employee:
        return ""
    
    # Apply filters based on designation
    if employee.designation == "Last Mile Manager":
        if employee.branch:
            conditions.append(f"`tabArea`.branch = '{employee.branch}'")
        else:
            # frappe.msgprint("Warning: Last Mile Manager has no branch assigned!")
            pass

    elif employee.designation == "Last Mile Head":
        if employee.branch:
            conditions.append(f"`tabArea`.branch = '{employee.branch}'")
            
    elif employee.designation == "Last Mile Zonal Head":
        # Check delivery mapping for multiple zones
        delivery_mapping = frappe.get_all(
            "Delivery Mapping",
            filters={"employee": employee.name},
            fields=["name"]
        )
        
        if delivery_mapping:
            zone_list = frappe.get_all(
                "Delivery Zone Mapping",
                filters={"parent": delivery_mapping[0].name},
                pluck="zone_name"
            )
            
            if zone_list:
                zones_str = "', '".join(zone_list)
                conditions.append(f"`tabArea`.zone_name in ('{zones_str}')")
            else:
                conditions.append("1=0")  # No access if no zones assigned
        else:
            conditions.append("1=0")  # No access if no delivery mapping
            
    elif employee.designation == "Last Mile Lead":
        # Check delivery mapping for multiple areas
        delivery_mapping = frappe.get_all(
            "Delivery Mapping",
            filters={"employee": employee.name},
            fields=["name"]
        )
        
        if delivery_mapping:
            area_list = frappe.get_all(
                "Delivery Area Mapping",
                filters={"parent": delivery_mapping[0].name},
                pluck="area_name"
            )
            
            if area_list:
                areas_str = "', '".join(area_list)
                conditions.append(f"`tabArea`.name in ('{areas_str}')")  # Using name field since area_name is part of the name
            else:
                conditions.append("1=0")  # No access if no areas assigned
        else:
            conditions.append("1=0")  # No access if no delivery mapping
    
    final_condition = " and ".join(conditions) if conditions else "1=1"
    return final_condition
