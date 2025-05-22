import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions for Attendance based on employee hierarchy:
    1. Checks if user has an employee record
    2. If yes, returns attendance records for all employees reporting to this user
    3. If no, returns default system permissions
    Returns: string - SQL condition
    """
    
    conditions = []
    
    # Log user and roles
    # frappe.msgprint(f"User: {user}, Roles: {frappe.get_roles(user)}")
    
    # Skip for System Manager or Administrator
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        # frappe.msgprint("User is System Manager or Administrator - no conditions applied")
        return " and ".join(conditions)
    
    # Get employee record for logged-in user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    # frappe.msgprint(f"Employee record found: {employee}")
    
    if not employee:
        # frappe.msgprint("No employee record found - using default permissions")
        return " and ".join(conditions)
    
    # For Last Mile Managers, show all employees in their branch
    if employee.designation == "Last Mile Manager":
        if employee.branch:
            conditions.append(f"custom_branch = '{employee.branch}'")
        return " and ".join(conditions)
    
    # Get all subordinates using MariaDB recursive query
    subordinates_query = """
        WITH RECURSIVE emp_hierarchy AS (
            /* Get direct subordinates first */
            SELECT name, reports_to, 1 as level
            FROM `tabEmployee`
            WHERE reports_to = %(employee)s

            UNION ALL
            
            /* Get subordinates of subordinates */
            SELECT e.name, e.reports_to, eh.level + 1
            FROM `tabEmployee` e
            INNER JOIN emp_hierarchy eh ON e.reports_to = eh.name
        )
        SELECT name FROM emp_hierarchy
    """
    subordinates = frappe.db.sql(subordinates_query, {"employee": employee}, as_dict=1)
    subordinate_names = [employee]  # Include self
    subordinate_names.extend([d.name for d in subordinates])
    # frappe.msgprint(f"Found subordinates: {subordinate_names}")
    
    # Add condition to show only subordinates' attendance records
    if subordinate_names:
        names_str = "','".join(subordinate_names)
        conditions.append(f"employee in ('{names_str}')")
        # frappe.msgprint(f"Final SQL condition: {' and '.join(conditions)}")
    
    return " and ".join(conditions)
