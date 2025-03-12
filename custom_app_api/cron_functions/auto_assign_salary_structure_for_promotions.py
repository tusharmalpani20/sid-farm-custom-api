import frappe
from datetime import datetime, timedelta, date
from frappe import _

def auto_assign_salary_structure():
    try:
        print("Starting automatic salary structure assignment process")
        
        # Get today's date in YYYY-MM-DD format
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get all promotions for today that are submitted (docstatus=1)
        promotions = frappe.get_all(
            "Employee Promotion",
            filters={
                "promotion_date": today,
                "docstatus": 1
            },
            fields=["name", "employee"],
            order_by="creation desc"
        )
        
        if not promotions:
            print(f"No promotions found for date: {today}")
            return
            
        print(f"Found {len(promotions)} promotion(s) to process")
        
        # Create a dict to track processed employees to handle duplicates
        processed_employees = set()
        successful_assignments = 0
        
        for promotion in promotions:
            try:
                if promotion.employee in processed_employees:
                    print(f"Skipping duplicate promotion for employee: {promotion.employee}")
                    continue
                    
                # Get the promotion doc to access child table
                promotion_doc = frappe.get_doc("Employee Promotion", promotion.name)
                
                # Find the designation change in promotion details
                new_designation = None
                for detail in promotion_doc.promotion_details:
                    if detail.property == "Designation":
                        new_designation = detail.new
                        break
                        
                # Skip if no designation change found
                if not new_designation:
                    print(f"No designation change found in promotion {promotion.name} for employee {promotion.employee}")
                    continue
                    
                processed_employees.add(promotion.employee)
                
                # Check if designation has a mapped salary structure
                salary_structure = frappe.db.get_value(
                    "Designation Salary Structure Mapping",
                    new_designation,
                    "salary_structure"
                )
                
                if not salary_structure:
                    print(f"No salary structure mapping found for designation {new_designation}. "
                          f"Promotion: {promotion.name}, Employee: {promotion.employee}")
                    continue
                    
                # Get employee details
                employee = frappe.get_doc("Employee", promotion.employee)
                
                # Check if there's already an assignment for this date
                existing_assignment = frappe.db.exists(
                    "Salary Structure Assignment",
                    {
                        "employee": promotion.employee,
                        "from_date": today,
                        "docstatus": 1
                    }
                )
                
                if existing_assignment:
                    print(f"Salary Structure Assignment already exists for employee {promotion.employee} "
                          f"on {today}. Promotion: {promotion.name}")
                    continue
                    
                # Create new salary structure assignment
                salary_assignment = frappe.get_doc({
                    "doctype": "Salary Structure Assignment",
                    "employee": promotion.employee,
                    "salary_structure": salary_structure,
                    "from_date": today,
                    "company": employee.company
                })
                
                salary_assignment.insert()
                salary_assignment.submit()
                
                frappe.db.commit()
                successful_assignments += 1
                
                print(f"Successfully created Salary Structure Assignment for employee {promotion.employee}. "
                      f"Promotion: {promotion.name}, New Designation: {new_designation}, "
                      f"Salary Structure: {salary_structure}")
                
                handle_salary_slip_creation(
                    employee=employee,
                    promotion_date=today,
                    salary_structure=salary_structure
                )
                
            except Exception as e:
                frappe.db.rollback()
                print(f"Error processing promotion {promotion.name} for employee {promotion.employee}: {str(e)}")
                
        # Log final summary
        print(f"Salary structure assignment process completed. "
              f"Total promotions: {len(promotions)}, "
              f"Successful assignments: {successful_assignments}, "
              f"Skipped/Failed: {len(promotions) - successful_assignments}")
        
    except Exception as e:
        print(f"Fatal error in auto_assign_salary_structure: {str(e)}")
        frappe.log_error(
            message=f"Fatal error in auto_assign_salary_structure: {str(e)}",
            title="Salary Structure Assignment Error"
        )

def handle_salary_slip_creation(employee, promotion_date, salary_structure):
    try:
        # Convert promotion_date to datetime if it's a date object
        if isinstance(promotion_date, date):
            promotion_dt = datetime.combine(promotion_date, datetime.min.time())
        else:
            promotion_dt = datetime.strptime(promotion_date, '%Y-%m-%d')
            
        month_start = frappe.utils.get_first_day(promotion_dt)
        month_end = frappe.utils.get_last_day(promotion_dt)
        
        print(f"Processing salary slips for employee {employee.name} "
              f"for promotion date {promotion_date}")
        
        # Get existing salary slips for this month
        existing_slips = frappe.get_all(
            "Salary Slip",
            filters={
                "employee": employee.name,
                "start_date": [">=", month_start],
                "end_date": ["<=", month_end],
                "docstatus": ["!=", 2]  # Not cancelled
            },
            fields=["name", "start_date", "end_date", "docstatus", "workflow_state"],
            order_by="start_date"
        )
        
        # Case 1: No existing salary slips - create new one directly
        if not existing_slips:
            create_salary_slip(
                employee=employee,
                start_date=month_start,
                end_date=month_end,
                salary_structure=salary_structure
            )
            return
            
        for slip in existing_slips:
            # Convert dates to datetime objects for comparison
            slip_start = datetime.combine(slip.start_date, datetime.min.time()) if isinstance(slip.start_date, date) else datetime.strptime(slip.start_date, '%Y-%m-%d')
            slip_end = datetime.combine(slip.end_date, datetime.min.time()) if isinstance(slip.end_date, date) else datetime.strptime(slip.end_date, '%Y-%m-%d')
            
            # Check if promotion date falls within this slip's period
            if slip_start <= promotion_dt <= slip_end:
                # Case 1: Submitted salary slip - skip processing
                if slip.docstatus == 1:
                    print(f"Found submitted salary slip {slip.name} covering promotion date. "
                          f"Skipping processing.")
                    return
                    
                # Case 2: Draft but already approved (not in pending) - skip processing
                if slip.docstatus == 0 and slip.workflow_state != "Pending":
                    print(f"Found approved draft salary slip {slip.name} covering promotion date. "
                          f"Skipping processing.")
                    return
                    
                # Case 3: Draft and pending - handle prorated calculation
                if slip.docstatus == 0 and slip.workflow_state == "Pending":
                    handle_prorated_salary_slip(
                        slip_name=slip.name,
                        employee=employee,
                        promotion_date=promotion_dt,
                        old_end_date=slip_end.date(),
                        new_salary_structure=salary_structure
                    )
                    return
                    
    except Exception as e:
        print(f"Error handling salary slip creation for employee {employee.name}: {str(e)}")
        frappe.log_error(message=str(e), title="Salary Slip Creation Error")

def handle_prorated_salary_slip(slip_name, employee, promotion_date, old_end_date, new_salary_structure):
    """Handle prorated salary calculation when promotion occurs mid-month"""
    try:
        # Get the existing salary slip
        existing_slip = frappe.get_doc("Salary Slip", slip_name)
        
        # Get basic salary from earnings
        basic_salary = 0
        for earning in existing_slip.earnings:
            if earning.salary_component == "Basic":
                basic_salary = earning.amount
                break
                
        if not basic_salary:
            print(f"No Basic salary component found in slip {slip_name}")
            return
            
        # Calculate days for proration
        days_until_promotion = (promotion_date.date() - existing_slip.start_date).days
        total_days = (existing_slip.end_date - existing_slip.start_date).days + 1
        
        # Calculate prorated amounts
        prorated_old_amount = (basic_salary / total_days) * days_until_promotion
        prorated_new_amount = (basic_salary / total_days) * (total_days - days_until_promotion)
        
        # 1. Cancel existing salary slip
        existing_slip.cancel()
        frappe.db.commit()
        
        # 2. Create Additional Salary for old salary structure period
        create_prorated_additional_salary(
            employee=employee,
            amount=prorated_old_amount,
            from_date=existing_slip.start_date,
            to_date=promotion_date.date() - timedelta(days=1),
            salary_component="Prorated Addition",
            reason=f"Prorated salary for period before promotion (Old Structure)"
        )
        
        # 3. Create new salary slip
        new_salary_slip = create_salary_slip(
            employee=employee,
            start_date=existing_slip.start_date,
            end_date=existing_slip.end_date,
            salary_structure=new_salary_structure
        )
        
        # 4. Create Additional Salary for deduction
        create_prorated_additional_salary(
            employee=employee,
            amount=-prorated_new_amount,  # Negative amount for deduction
            from_date=promotion_date.date(),
            to_date=existing_slip.end_date,
            salary_component="Prorated Deduction",
            reason=f"Prorated salary adjustment for period after promotion (New Structure)"
        )
        
        print(f"Successfully handled prorated salary for employee {employee.name}")
        
    except Exception as e:
        print(f"Error handling prorated salary: {str(e)}")
        frappe.log_error(message=str(e), title="Prorated Salary Processing Error")

def create_prorated_additional_salary(employee, amount, from_date, to_date, salary_component, reason):
    """Create Additional Salary entry for prorated amount"""
    try:
        additional_salary = frappe.get_doc({
            "doctype": "Additional Salary",
            "employee": employee.name,
            "salary_component": salary_component,
            "amount": amount,
            "payroll_date": from_date,
            "from_date": from_date,
            "to_date": to_date,
            "company": employee.company,
            "custom_reason": reason,
            "overwrite_salary_structure_amount": 0
        })
        
        # Bypass workflow and permissions
        additional_salary.flags.ignore_permissions = True
        additional_salary.flags.ignore_validate = True
        additional_salary.flags.ignore_mandatory = True
        additional_salary.flags.ignore_workflow = True
        
        additional_salary.insert()
        
        # Set workflow state and docstatus directly
        frappe.db.set_value('Additional Salary', additional_salary.name, {
            'workflow_state': 'Submitted',
            'docstatus': 1
        })
        
        additional_salary.reload()
        
        return additional_salary
        
    except Exception as e:
        print(f"Error creating additional salary: {str(e)}")
        frappe.log_error(message=str(e), title="Additional Salary Creation Error")

def create_salary_slip(employee, start_date, end_date, salary_structure):
    """Create a new salary slip for the given period"""
    try:
        # Check if a salary slip already exists for this period
        existing_slip = frappe.db.exists(
            "Salary Slip",
            {
                "employee": employee.name,
                "start_date": start_date,
                "end_date": end_date,
                "docstatus": ["!=", 2]  # Not cancelled
            }
        )
        
        if existing_slip:
            print(f"Salary slip already exists for employee {employee.name} "
                  f"from {start_date} to {end_date}. Skipping creation.")
            return
            
        salary_slip = frappe.get_doc({
            "doctype": "Salary Slip",
            "employee": employee.name,
            "salary_structure": salary_structure,
            "start_date": start_date,
            "end_date": end_date,
            "company": employee.company
        })
        
        salary_slip.insert()
        
        print(f"Created new salary slip for employee {employee.name} "
              f"from {start_date} to {end_date} with structure {salary_structure}")
        
    except Exception as e:
        print(f"Error creating salary slip for employee {employee.name}: {str(e)}")
