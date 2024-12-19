import frappe
from frappe.utils import now_datetime, today

def after_save(doc, method):
    # Get the previous document state
    old_doc = doc.get_doc_before_save()
    if not old_doc:
        return

    # Case 1: Reset fields only when:
    # - Status is being changed TO Active FROM something else, OR
    # - Notice period is being unchecked (changed from checked to unchecked)
    if (
        (doc.status == "Active" and old_doc.status != "Active") or
        (doc.custom_is_notice_period == 0 and old_doc.custom_is_notice_period == 1)
    ):
        # Reset all notice period related fields
        doc.db_set({
            'custom_is_notice_period': 0,
            'custom_notice_period_marked_at': None,
            'relieving_date': None,
            'status': 'Active'
        }, update_modified=False)

        # Close any open job openings for this route
        if doc.grade == "L5" and doc.custom_route:
            close_open_job_openings(doc)
        return

    # Case 2: Direct status change to Left
    if doc.status == "Left" and not doc.custom_is_notice_period:
        doc.db_set({
            'custom_is_notice_period': 1,
            'custom_notice_period_marked_at': now_datetime(),
            'relieving_date': today()
        }, update_modified=False)
        
        # Create job opening if employee is L5 grade
        if doc.grade == "L5" and doc.custom_route:
            create_job_opening_for_route(doc)
        return

    # Case 3: Normal notice period flow
    if doc.custom_is_notice_period:
        # Update notice period marked timestamp
        doc.db_set('custom_notice_period_marked_at', now_datetime(), update_modified=False)
        
        # If notice days is zero, set relieving date and status
        if doc.notice_number_of_days == 0:
            doc.db_set({
                'relieving_date': today(),
                'status': 'Left'
            }, update_modified=False)

            if doc.grade == "L5" and doc.custom_route:
                create_job_opening_for_route(doc)

def close_open_job_openings(employee_doc):
    try:
        # Find any open job openings for this route
        open_job_openings = frappe.get_all(
            "Job Opening",
            filters={
                "custom_travel_route": employee_doc.custom_route,
                "status": "Open"
            },
            fields=["name"]
        )

        for job_opening in open_job_openings:
            frappe.db.set_value(
                "Job Opening",
                job_opening.name,
                {
                    "status": "Closed",
                    "closed_on": now_datetime()
                },
                update_modified=True
            )

        if open_job_openings:
            frappe.logger().info(
                f"Closed {len(open_job_openings)} job opening(s) for route {employee_doc.custom_route} "
                f"as employee {employee_doc.name} is now Active"
            )
            frappe.db.commit()

    except Exception as e:
        frappe.log_error(
            message=f"Error closing job openings for route {employee_doc.custom_route}: {frappe.get_traceback()}",
            title=f"Job Opening Closure Error - {employee_doc.name}"
        )

def create_job_opening_for_route(employee_doc):
    try:
        # Check if there's already an open job opening for this route
        existing_opening = frappe.get_all(
            "Job Opening",
            filters={
                "custom_travel_route": employee_doc.custom_route,
                "status": "Open"
            }
        )

        if not existing_opening:
            job_opening = frappe.get_doc({
                "doctype": "Job Opening",
                "job_title": f"Vacancy for {employee_doc.custom_route}",
                "designation": employee_doc.designation or "Delivery Partner",
                "status": "Open",
                "posted_on": now_datetime(),
                "company": "SIDS FARM PRIVATE LIMITED",
                "custom_travel_route": employee_doc.custom_route,
                "location": employee_doc.branch,
                "route": f"jobs/sids_farm_private_limited/{employee_doc.custom_route.lower()}"
            })

            job_opening.insert(ignore_permissions=True)
            frappe.db.commit()

            frappe.logger().info(
                f"Created job opening for route {employee_doc.custom_route} "
                f"due to notice period of employee {employee_doc.name}"
            )

    except Exception as e:
        frappe.log_error(
            message=f"Error creating job opening for route {employee_doc.custom_route}: {frappe.get_traceback()}",
            title=f"Notice Period Job Opening Creation Error - {employee_doc.name}"
        )
        
        