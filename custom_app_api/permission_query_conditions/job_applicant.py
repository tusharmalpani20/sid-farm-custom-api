import frappe

def get_permission_query_conditions(user):
    """
    Adds permission conditions for Job Applicant doctype based on employee's route access:
    - System Manager/Administrator: No restrictions
    - Last Mile Head/Zonal Head/Lead: Access to job applicants based on their assigned routes via Job Opening
    Returns: string - SQL condition
    """
    
    # Skip for System Manager or Administrator
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return ""
    
    # Get the job openings accessible to the user
    job_opening_condition = frappe.get_attr("custom_app_api.permission_query_conditions.job_opening.get_permission_query_conditions")(user)
    
    if not job_opening_condition:
        return ""
    
    # Create condition to join Job Applicant with Job Opening
    condition = f"""exists (
        select name from `tabJob Opening` 
        where name = `tabJob Applicant`.job_title 
        and {job_opening_condition}
    )"""
    
    return condition
