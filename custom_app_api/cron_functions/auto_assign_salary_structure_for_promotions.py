import frappe
from datetime import datetime, timedelta
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
                "workflow_state": ["not in", ["Pending"]]
            },
            fields=["name", "start_date", "end_date", "docstatus", "workflow_state"],
            order_by="start_date"
        )
        print(existing_slips)
        # Case 1: No existing salary slips
        if not existing_slips:
            create_salary_slip(
                employee=employee,
                start_date=promotion_date,
                end_date=month_end,
                salary_structure=salary_structure
            )
            return
        
        # Separate submitted and draft slips
        submitted_slips = [slip for slip in existing_slips if slip.docstatus == 1]
        draft_slips = [slip for slip in existing_slips if slip.docstatus == 0]
        
        # Handle submitted slips first
        for slip in submitted_slips:
            slip_start = datetime.strptime(slip.start_date, '%Y-%m-%d')
            slip_end = datetime.strptime(slip.end_date, '%Y-%m-%d')
            
            # If promotion date falls within a submitted slip period
            if slip_start <= promotion_dt <= slip_end:
                # Check if there's remaining period in the month after this slip
                if slip_end < datetime.strptime(month_end, '%Y-%m-%d'):
                    create_salary_slip(
                        employee=employee,
                        start_date=(slip_end + timedelta(days=1)).strftime('%Y-%m-%d'),
                        end_date=month_end,
                        salary_structure=salary_structure
                    )
                print(f"Found submitted salary slip covering promotion date. "
                      f"Slip: {slip.name}, Period: {slip.start_date} to {slip.end_date}")
                return
            
            # If promotion date is after this submitted slip
            if promotion_dt > slip_end:
                create_salary_slip(
                    employee=employee,
                    start_date=promotion_date,
                    end_date=month_end,
                    salary_structure=salary_structure
                )
                return
        
        # Handle draft slips
        for slip in draft_slips:
            slip_start = datetime.strptime(slip.start_date, '%Y-%m-%d')
            slip_end = datetime.strptime(slip.end_date, '%Y-%m-%d')
            
            # If slip is in draft and covers promotion date
            if slip_start <= promotion_dt <= slip_end:
                # Update existing draft slip to end before promotion
                existing_slip = frappe.get_doc("Salary Slip", slip.name)
                existing_slip.end_date = (promotion_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                existing_slip.save()
                
                print(f"Updated existing draft salary slip {slip.name} to end on "
                      f"{existing_slip.end_date}")
                
                # Create new slip from promotion date
                create_salary_slip(
                    employee=employee,
                    start_date=promotion_date,
                    end_date=month_end,
                    salary_structure=salary_structure
                )
                return
                
    except Exception as e:
        print(f"Error handling salary slip creation for employee {employee.name}: {str(e)}")

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
