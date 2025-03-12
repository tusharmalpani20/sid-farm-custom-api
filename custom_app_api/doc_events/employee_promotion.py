import frappe
from frappe.utils import now_datetime, today
from datetime import datetime

def check_duplicate_promotions(doc):
    """Check if there's already a promotion for this employee in the same month (draft or submitted)"""
    # Get current month and year from promotion date
    promotion_date = datetime.strptime(doc.promotion_date, '%Y-%m-%d')
    current_month = promotion_date.month
    current_year = promotion_date.year
    
    # Check for existing promotions for this employee in the same month
    existing_promotions = frappe.get_all(
        "Employee Promotion",
        filters={
            "employee": doc.employee,
            "docstatus": ["in", [0, 1]],  # Both draft and submitted documents
            "name": ["!=", doc.name]  # Exclude current document
        },
        fields=["name", "promotion_date", "docstatus"]
    )
    
    # Check if any existing promotion is in the same month
    for promotion in existing_promotions:
        existing_date = datetime.strptime(promotion.promotion_date, '%Y-%m-%d')
        if existing_date.month == current_month and existing_date.year == current_year:
            status = "Draft" if promotion.docstatus == 0 else "Submitted"
            frappe.throw(f"Cannot save promotion. Employee {doc.employee} already has a {status} promotion (Document: {promotion.name}) in the same month.")

def before_save(doc, method):
    # Check for duplicate promotions in the same month
    check_duplicate_promotions(doc)

def before_submit(doc, method):
    """Additional check before submission"""
    check_duplicate_promotions(doc)
