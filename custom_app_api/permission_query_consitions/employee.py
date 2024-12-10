import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions based on employee hierarchy:
    1. Checks if user has an employee record
    2. If yes, returns all employees reporting to this user (direct + indirect reports)
    3. If no, returns default system permissions
    Returns: string - SQL condition
    """
    conditions = ["status = 'Inactive'"]
    
    # # Skip for System Manager or Administrator
    # if "System Manager" in frappe.get_roles(user) or user == "Administrator":
    #     return " and ".join(conditions)
    
    # # Get employee record for logged-in user
    # employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    # if not employee:
    #     return " and ".join(conditions)  # Return default permissions if no employee record
    
    # # Get all subordinates using MariaDB recursive query
    # subordinates_query = """
    #     WITH RECURSIVE emp_hierarchy AS (
    #         /* Get direct subordinates first */
    #         SELECT name, reports_to, 1 as level
    #         FROM `tabEmployee`
    #         WHERE reports_to = %(employee)s

    #         UNION ALL
            
    #         /* Get subordinates of subordinates */
    #         SELECT e.name, e.reports_to, eh.level + 1
    #         FROM `tabEmployee` e
    #         INNER JOIN emp_hierarchy eh ON e.reports_to = eh.name
    #     )
    #     SELECT name FROM emp_hierarchy
    # """
    # subordinates = frappe.db.sql(subordinates_query, {"employee": employee}, as_dict=1)
    # subordinate_names = [employee]  # Include self
    # subordinate_names.extend([d.name for d in subordinates])
    
    # # Add debug print to show the list of IDs
    # frappe.msgprint(f"Subordinate IDs: {subordinate_names}")
    
    # # Add condition to show only subordinates
    # if subordinate_names:
    #     conditions.append("""name in ({})""".format(
    #         ', '.join(['%s'] * len(subordinate_names))
    #     ) % tuple(subordinate_names))
    
    return " and ".join(conditions)
