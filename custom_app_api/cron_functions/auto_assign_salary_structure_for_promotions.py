import frappe
from datetime import datetime
from frappe import _

def auto_assign_salary_structure():
    try:
        frappe.logger().info("Starting automatic salary structure assignment process")
        
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
            frappe.logger().info(f"No promotions found for date: {today}")
            return
            
        frappe.logger().info(f"Found {len(promotions)} promotion(s) to process")
        
        # Create a dict to track processed employees to handle duplicates
        processed_employees = set()
        successful_assignments = 0
        
        for promotion in promotions:
            try:
                if promotion.employee in processed_employees:
                    frappe.logger().info(f"Skipping duplicate promotion for employee: {promotion.employee}")
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
                    frappe.logger().warning(
                        f"No designation change found in promotion {promotion.name} for employee {promotion.employee}"
                    )
                    continue
                    
                processed_employees.add(promotion.employee)
                
                # Check if designation has a mapped salary structure
                salary_structure = frappe.db.get_value(
                    "Designation Salary Structure Mapping",
                    new_designation,
                    "salary_structure"
                )
                
                if not salary_structure:
                    frappe.logger().error(
                        f"No salary structure mapping found for designation {new_designation}. "
                        f"Promotion: {promotion.name}, Employee: {promotion.employee}"
                    )
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
                    frappe.logger().warning(
                        f"Salary Structure Assignment already exists for employee {promotion.employee} "
                        f"on {today}. Promotion: {promotion.name}"
                    )
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
                
                frappe.logger().info(
                    f"Successfully created Salary Structure Assignment for employee {promotion.employee}. "
                    f"Promotion: {promotion.name}, New Designation: {new_designation}, "
                    f"Salary Structure: {salary_structure}"
                )
                
            except Exception as e:
                frappe.db.rollback()
                frappe.logger().error(
                    f"Error processing promotion {promotion.name} for employee {promotion.employee}: {str(e)}"
                )
                
        # Log final summary
        frappe.logger().info(
            f"Salary structure assignment process completed. "
            f"Total promotions: {len(promotions)}, "
            f"Successful assignments: {successful_assignments}, "
            f"Skipped/Failed: {len(promotions) - successful_assignments}"
        )
        
    except Exception as e:
        frappe.logger().error(f"Fatal error in auto_assign_salary_structure: {str(e)}")
        frappe.log_error(
            message=f"Fatal error in auto_assign_salary_structure: {str(e)}",
            title="Salary Structure Assignment Error"
        )
