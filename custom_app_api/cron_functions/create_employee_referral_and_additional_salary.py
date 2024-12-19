import frappe
from frappe.utils import now_datetime

def create_employee_referral_for_job_applicant(doc, method):
    """
    Create Employee Referral when a new Job Applicant is created with a source_name
    and update the Job Applicant with the created referral ID
    """
    if not doc.source_name:
        return

    # Split the applicant name into first and last name
    name_parts = (doc.applicant_name or "").split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Create Employee Referral
    employee_referral = frappe.get_doc({
        "doctype": "Employee Referral",
        "first_name": first_name,
        "last_name": last_name,
        "full_name": doc.applicant_name,
        "date": now_datetime(),
        "status": "Pending",
        "for_designation": doc.designation,
        "email": doc.email_id,
        "contact_no": doc.phone_number,
        "referrer": doc.source_name,
        "is_applicable_for_referral_bonus": 1
    })

    employee_referral.insert(ignore_permissions=True)

    # Update Job Applicant with the created Employee Referral
    frappe.db.set_value('Job Applicant', doc.name, 'employee_referral', employee_referral.name)
