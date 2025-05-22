import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions for Point doctype based on employee hierarchy and geographical assignments:
    - System Manager/Administrator: No restrictions
    - Last Mile Manager: Access to all points in their branch
    - Last Mile Head: Access to points in their branch
    - Last Mile Zonal Head: Access to points in their zone
    - Last Mile Lead: Access to points in their area
    Returns: string - SQL condition
    """
    
    # frappe.msgprint(f"Permission check for user: {user}")
    conditions = []
    
    # Skip for System Manager or Administrator
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        # frappe.msgprint("User is System Manager or Administrator - No restrictions")
        return ""
    
    # Get employee record for logged-in user
    employee = frappe.db.get_value("Employee", 
        {"user_id": user}, 
        ["name", "designation", "branch", "custom_zone", "custom_area"],
        as_dict=1
    )
    
    # frappe.msgprint(f"Employee found: {employee}")
    
    if not employee:
        # frappe.msgprint("No employee record found - Using default permissions")
        return ""
    
    # frappe.msgprint(f"Checking filters for designation: {employee.designation}")
    
    # Apply filters based on designation
    if employee.designation == "Last Mile Manager":
        if employee.branch:
            conditions.append(f"`tabZone`.branch = '{employee.branch}'")
        else:
            # frappe.msgprint("Warning: Last Mile Manager has no branch assigned!")
            pass

    elif employee.designation == "Last Mile Head":
        if employee.branch:
            conditions.append(f"`tabPoint`.branch = '{employee.branch}'")
            # frappe.msgprint(f"Last Mile Head filter applied for branch: {employee.branch}")
        # else:
            # frappe.msgprint("Warning: Last Mile Head has no branch assigned!")
            
    elif employee.designation == "Last Mile Zonal Head":
        # Check delivery mapping for multiple zones
        delivery_mapping = frappe.get_all(
            "Delivery Mapping",
            filters={"employee": employee.name},
            fields=["name"]
        )
        
        if delivery_mapping:
            # frappe.msgprint(f"Found delivery mapping for Zonal Head")
            zone_list = frappe.get_all(
                "Delivery Zone Mapping",
                filters={"parent": delivery_mapping[0].name},
                pluck="zone_name"
            )
            
            if zone_list:
                zones_str = "', '".join(zone_list)
                conditions.append(f"`tabPoint`.zone_name in ('{zones_str}')")
                # frappe.msgprint(f"Last Mile Zonal Head filter applied for zones: {zones_str}")
            else:
                # frappe.msgprint("Warning: No zones found in delivery mapping!")
                conditions.append("1=0")  # No access if no zones assigned
        else:
            # frappe.msgprint("Warning: No delivery mapping found for Zonal Head!")
            conditions.append("1=0")  # No access if no delivery mapping
            
    elif employee.designation == "Last Mile Lead":
        # Check delivery mapping for multiple areas
        delivery_mapping = frappe.get_all(
            "Delivery Mapping",
            filters={"employee": employee.name},
            fields=["name"]
        )
        
        if delivery_mapping:
            # frappe.msgprint(f"Found delivery mapping for Lead")
            area_list = frappe.get_all(
                "Delivery Area Mapping",
                filters={"parent": delivery_mapping[0].name},
                pluck="area_name"
            )
            
            if area_list:
                areas_str = "', '".join(area_list)
                conditions.append(f"`tabPoint`.area_name in ('{areas_str}')")
                # frappe.msgprint(f"Last Mile Lead filter applied for areas: {areas_str}")
            else:
                # frappe.msgprint("Warning: No areas found in delivery mapping!")
                conditions.append("1=0")  # No access if no areas assigned
        else:
            # frappe.msgprint("Warning: No delivery mapping found for Lead!")
            conditions.append("1=0")  # No access if no delivery mapping
    
    final_condition = " and ".join(conditions) if conditions else "1=1"
    # frappe.msgprint(f"Final condition: {final_condition}")
    
    return final_condition
