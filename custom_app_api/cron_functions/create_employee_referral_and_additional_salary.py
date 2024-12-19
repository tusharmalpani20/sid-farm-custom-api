import frappe
from frappe.utils import now_datetime

def create_employee_referral_for_job_applicant(doc, method):
    """
    Create Employee Referral when a new Job Applicant is created with a source_name
    and update the Job Applicant with the created referral ID
    """
    if not doc.source_name:
        return

    # Handle the name splitting with better fallbacks
    full_name = (doc.applicant_name or "").strip()
    name_parts = full_name.split(maxsplit=1)
    
    if len(name_parts) > 1:
        first_name = name_parts[0]
        last_name = name_parts[1]
    else:
        # If only one name provided (e.g., "Test")
        first_name = full_name
        last_name = full_name  # Option 1: Use same name
        # OR
        # last_name = "." # Option 2: Use a period
        # OR
        # last_name = "NA" # Option 3: Use NA
        # OR
        # last_name = first_name + " (LN)" # Option 4: Add a suffix

    employee_referral = frappe.get_doc({
        "doctype": "Employee Referral",
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "date": now_datetime(),
        "status": "Pending",
        "for_designation": doc.designation or "Delivery Partner",
        "email": doc.email_id,
        "contact_no": doc.phone_number,
        "referrer": doc.source_name,
        "is_applicable_for_referral_bonus": 1
    })

    employee_referral.insert(ignore_permissions=True)
    employee_referral.submit()

    # Update Job Applicant with the created Employee Referral
    frappe.db.set_value('Job Applicant', doc.name, 'employee_referral', employee_referral.name)

    # Update employee referral status to In Process
    frappe.db.set_value('Employee Referral', employee_referral.name, 'status', 'In Process')
def process_referral_bonuses():
    """
    Cron job to process referral bonuses for employees who referred L5 grade employees
    that have completed 3 months with the company.
    Runs daily.
    """
    try:
        frappe.logger().info("Starting referral bonus processing")
        
        unpaid_referrals = frappe.get_all(
            "Employee Referral",
            filters={
                "status": "Accepted",
                "referral_payment_status": "Unpaid",
                "is_applicable_for_referral_bonus": 1
            },
            fields=["name", "email", "contact_no", "referrer"]
        )
        
        frappe.logger().info(f"Found {len(unpaid_referrals)} unpaid referrals to process")

        for referral in unpaid_referrals:
            frappe.logger().info(f"Processing referral {referral.name} for referrer {referral.referrer}")
            
            # Find if referred person is an employee
            referred_employee = frappe.db.get_value(
                "Employee",
                {
                    "personal_email": referral.email,
                    "cell_number": referral.contact_no,
                    "grade": "L5",
                    "status": "Active"
                },
                ["name", "date_of_joining", "company"],
                as_dict=1
            )

            if not referred_employee:
                frappe.logger().info(f"No matching L5 grade employee found for referral {referral.name}")
                continue

            # Check if employee has completed 3 months
            months_employed = frappe.utils.date_diff(
                frappe.utils.today(),
                referred_employee.date_of_joining
            ) / 30.0

            if months_employed < 3:
                frappe.logger().info(
                    f"Employee {referred_employee.name} has only completed {int(months_employed)} months. "
                    "Minimum 3 months required."
                )
                continue

            # Check if referrer is still an active employee
            referrer = frappe.db.get_value(
                "Employee",
                {
                    "name": referral.referrer,
                    "status": "Active"
                },
                ["name", "employee_name"],
                as_dict=1
            )

            if not referrer:
                frappe.logger().info(f"Referrer {referral.referrer} is not an active employee")
                continue

            frappe.logger().info(
                f"Creating referral bonus for {referrer.employee_name}. "
                f"Referred employee: {referred_employee.name}, Months completed: {int(months_employed)}"
            )

            # Create Additional Salary for referrer
            bonus_amount = 500  # Set your bonus amount here

            reason = (
                f"Referral Bonus for referring {referred_employee.name}\n"
                f"Referred Employee Join Date: {referred_employee.date_of_joining}\n"
                f"Months Completed: {int(months_employed)}"
            )

            additional_salary = frappe.get_doc({
                "doctype": "Additional Salary",
                "employee": referrer.name,
                "salary_component": "Referral Bonus",
                "amount": bonus_amount,
                "payroll_date": frappe.utils.today(),
                "company": referred_employee.company,
                "ref_doctype": "Employee Referral",
                "ref_docname": referral.name,
                "custom_reason": reason,
                "overwrite_salary_structure_amount": 1
            })

            # Bypass workflow and permissions
            additional_salary.flags.ignore_permissions = True
            additional_salary.flags.ignore_validate = True
            additional_salary.flags.ignore_mandatory = True
            additional_salary.flags.ignore_workflow = True
            
            # Insert without triggering workflow
            additional_salary.insert()
            
            # Force update workflow state in database directly
            frappe.db.set_value('Additional Salary', additional_salary.name, 'workflow_state', 'Submitted')
            
            # Now submit the document
            additional_salary.submit()

            # Update referral status to Paid
            frappe.db.set_value("Employee Referral", referral.name, "referral_payment_status", "Paid")
            frappe.db.commit()

            frappe.logger().info(
                f"Referral bonus created for {referrer.employee_name} "
                f"for referring {referred_employee.name}. Amount: Rs. {bonus_amount}"
            )

    except Exception as e:
        frappe.logger().error(f"Error in process_referral_bonuses: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Process Referral Bonuses Error")


