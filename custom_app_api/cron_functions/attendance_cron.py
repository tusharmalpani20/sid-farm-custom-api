import frappe
from frappe import _
from typing import Dict, Any, Optional
from custom_app_api.custom_api.helper_function.calculate_distance import calculate_total_distance
import time

def auto_mark_employee_absent_and_submit_all_todays_attendance() -> None:
    """
    Scheduled job to mark absent for employees with no attendance record
    Designed to run at the end of each day via scheduler
    """
    start_time = time.time()
    try:
        today = frappe.utils.nowdate()
        # today = frappe.utils.add_days(frappe.utils.nowdate(), -1)
        
        # Get all active employees
        employee_start_time = time.time()
        active_employees = frappe.get_all(
            "Employee",
            filters={
                "status": "Active",
                "date_of_joining": ["<=", today]
            },
            fields=["name", "employee_name", "company", "department", "custom_route"]
        )
        print(f"Time taken to fetch active employees: {time.time() - employee_start_time:.2f} seconds")

        if not active_employees:
            print("No active employees found for marking absent")
            return

        # Get today's attendance records with full documents
        attendance_fetch_start = time.time()
        existing_attendance = frappe.db.get_all(
            "Attendance",
            filters={
                "attendance_date": today,
                "docstatus": ["in", [0, 1]]  # Include both draft and submitted
            },
            fields=["*"]
        )
        print(f"Time taken to fetch existing attendance: {time.time() - attendance_fetch_start:.2f} seconds")

        # Create set of employees who already have attendance
        employees_with_attendance = {att.employee for att in existing_attendance}
        
        # Create absent records for employees without attendance
        absent_marking_start = time.time()
        absent_count = 0
        error_count = 0
        submitted_count = 0

        for employee in active_employees:
            if employee.name not in employees_with_attendance:
                employee_start = time.time()
                try:
                    # Prepare attendance data
                    attendance_data = {
                        "doctype": "Attendance",
                        "employee": employee.name,
                        "employee_name": employee.employee_name,
                        "attendance_date": today,
                        "status": "Absent",
                        "company": employee.company,
                        "department": employee.department
                    }

                    # Add custom_route and fetch total_delivery from Route
                    if employee.custom_route:
                        attendance_data["custom_route"] = employee.custom_route
                        
                        # # Get total_delivery from Route doctype
                        # route_total_delivery = frappe.db.get_value(
                        #     "Route",
                        #     employee.custom_route,
                        #     "total_delivery"
                        # )
                        
                        # if route_total_delivery:
                        #     attendance_data["custom_total_deliveries"] = route_total_delivery
                    
                    # Create new attendance record
                    attendance = frappe.get_doc(attendance_data)
                    attendance.insert()
                    attendance.submit()
                    absent_count += 1
                    
                    if absent_count % 10 == 0:  # Log every 10 records
                        print(f"Processed {absent_count} absent records. Last record took: {time.time() - employee_start:.2f} seconds")
                    
                except Exception as e:
                    error_count += 1
                    frappe.log_error(
                        message=f"Error marking absent for employee {employee.name}: {str(e)}",
                        title="Auto Mark Absent Error"
                    )

        print(f"Time taken for absent marking: {time.time() - absent_marking_start:.2f} seconds")

        # Submit all draft attendance records
        draft_submission_start = time.time()
        for idx, attendance_record in enumerate(existing_attendance):
            if attendance_record.docstatus == 0:  # Draft state
                record_start = time.time()
                try:
                    attendance_doc = frappe.get_doc("Attendance", attendance_record.name)
                    
                    # Only process route tracking if there was a punch in
                    if attendance_doc.custom_mobile_punch_in_at:
                        # Get route tracking records for this attendance
                        route_fetch_start = time.time()
                        route_records = frappe.db.sql("""
                            SELECT latitude, longitude, recorded_at
                            FROM `tabRoute Tracking`
                            WHERE attendance = %s
                            ORDER BY recorded_at ASC
                        """, (attendance_record.name,), as_dict=1)
                        print(f"Time taken to fetch route records for attendance {attendance_record.name}: {time.time() - route_fetch_start:.2f} seconds")
                        
                        # Calculate total distance if route records exist
                        if route_records:
                            distance_calc_start = time.time()
                            coordinates = [[record.latitude, record.longitude] 
                                        for record in route_records]
                            total_distance = calculate_total_distance(coordinates)
                            
                            # Update the attendance record with total distance
                            attendance_doc.custom_kilometers_travelled = total_distance
                            print(f"Time taken to calculate distance for attendance {attendance_record.name}: {time.time() - distance_calc_start:.2f} seconds")
                    
                    # Only set punch out time if it hasn't been set yet
                    if not attendance_doc.custom_mobile_punch_out_at:
                        attendance_doc.custom_mobile_punch_out_at = frappe.utils.now()
                        attendance_doc.custom_is_mobile_auto_punch_out = 1
                    
                    attendance_doc.submit()
                    submitted_count += 1
                    
                    if submitted_count % 10 == 0:  # Log every 10 records
                        print(f"Processed {submitted_count} draft submissions. Last record took: {time.time() - record_start:.2f} seconds")
                    
                except Exception as e:
                    error_count += 1
                    frappe.log_error(
                        message=f"Error submitting attendance {attendance_record.name}: {str(e)}",
                        title="Auto Submit Attendance Error"
                    )

        print(f"Time taken for draft submission: {time.time() - draft_submission_start:.2f} seconds")

        # Log summary
        print(
            f"Auto Mark Absent Summary - Date: {today}\n"
            f"Total Active Employees: {len(active_employees)}\n"
            f"Existing Attendance: {len(existing_attendance)}\n"
            f"Marked Absent: {absent_count}\n"
            f"Submitted: {submitted_count}\n"
            f"Errors: {error_count}\n"
            f"Total execution time: {time.time() - start_time:.2f} seconds"
        )

    except Exception as e:
        frappe.log_error(
            message=f"Error in auto mark absent job: {str(e)}",
            title="Auto Mark Absent Job Failed"
        )

def auto_mark_employee_absent_and_submit_all_attendance_for_a_specific_date() -> None:
    """
    Scheduled job to mark absent for employees with no attendance record
    Designed to run at the end of each day via scheduler
    """
    start_time = time.time()
    try:
        today = "2025-07-05"
        print(f"Running for date: {today}")
        # today = frappe.utils.add_days(frappe.utils.nowdate(), -1)
        
        # Get all active employees
        employee_start_time = time.time()
        active_employees = frappe.get_all(
            "Employee",
            filters={
                "status": "Active",
                "date_of_joining": ["<=", today]
            },
            fields=["name", "employee_name", "company", "department", "custom_route"]
        )
        print(f"Time taken to fetch active employees: {time.time() - employee_start_time:.2f} seconds")

        if not active_employees:
            print("No active employees found for marking absent")
            return

        # Get today's attendance records with full documents
        attendance_fetch_start = time.time()
        existing_attendance = frappe.db.get_all(
            "Attendance",
            filters={
                "attendance_date": today,
                "docstatus": ["in", [0, 1]]  # Include both draft and submitted
            },
            fields=["*"]
        )
        print(f"Time taken to fetch existing attendance: {time.time() - attendance_fetch_start:.2f} seconds")

        # Create set of employees who already have attendance
        employees_with_attendance = {att.employee for att in existing_attendance}
        
        # Create absent records for employees without attendance
        absent_marking_start = time.time()
        absent_count = 0
        error_count = 0
        submitted_count = 0

        for employee in active_employees:
            if employee.name not in employees_with_attendance:
                employee_start = time.time()
                try:
                    # Prepare attendance data
                    attendance_data = {
                        "doctype": "Attendance",
                        "employee": employee.name,
                        "employee_name": employee.employee_name,
                        "attendance_date": today,
                        "status": "Absent",
                        "company": employee.company,
                        "department": employee.department
                    }

                    # Add custom_route and fetch total_delivery from Route
                    if employee.custom_route:
                        attendance_data["custom_route"] = employee.custom_route
                        
                        # # Get total_delivery from Route doctype
                        # route_total_delivery = frappe.db.get_value(
                        #     "Route",
                        #     employee.custom_route,
                        #     "total_delivery"
                        # )
                        
                        # if route_total_delivery:
                        #     attendance_data["custom_total_deliveries"] = route_total_delivery
                    
                    # Create new attendance record
                    attendance = frappe.get_doc(attendance_data)
                    attendance.insert()
                    attendance.submit()
                    absent_count += 1
                    
                    if absent_count % 10 == 0:  # Log every 10 records
                        print(f"Processed {absent_count} absent records. Last record took: {time.time() - employee_start:.2f} seconds")
                    
                except Exception as e:
                    error_count += 1
                    frappe.log_error(
                        message=f"Error marking absent for employee {employee.name}: {str(e)}",
                        title="Auto Mark Absent Error"
                    )

        print(f"Time taken for absent marking: {time.time() - absent_marking_start:.2f} seconds")

        # Submit all draft attendance records
        draft_submission_start = time.time()
        for idx, attendance_record in enumerate(existing_attendance):
            if attendance_record.docstatus == 0:  # Draft state
                record_start = time.time()
                try:
                    attendance_doc = frappe.get_doc("Attendance", attendance_record.name)
                    
                    # Only process route tracking if there was a punch in
                    if attendance_doc.custom_mobile_punch_in_at:
                        # Get route tracking records for this attendance
                        route_fetch_start = time.time()
                        route_records = frappe.db.sql("""
                            SELECT latitude, longitude, recorded_at
                            FROM `tabRoute Tracking`
                            WHERE attendance = %s
                            ORDER BY recorded_at ASC
                        """, (attendance_record.name,), as_dict=1)
                        print(f"Time taken to fetch route records for attendance {attendance_record.name}: {time.time() - route_fetch_start:.2f} seconds")
                        
                        # Calculate total distance if route records exist
                        if route_records:
                            distance_calc_start = time.time()
                            coordinates = [[record.latitude, record.longitude] 
                                        for record in route_records]
                            total_distance = calculate_total_distance(coordinates)
                            
                            # Update the attendance record with total distance
                            attendance_doc.custom_kilometers_travelled = total_distance
                            print(f"Time taken to calculate distance for attendance {attendance_record.name}: {time.time() - distance_calc_start:.2f} seconds")
                    
                    # Only set punch out time if it hasn't been set yet
                    if not attendance_doc.custom_mobile_punch_out_at:
                        attendance_doc.custom_mobile_punch_out_at = frappe.utils.now()
                        attendance_doc.custom_is_mobile_auto_punch_out = 1
                    
                    attendance_doc.submit()
                    submitted_count += 1
                    
                    if submitted_count % 10 == 0:  # Log every 10 records
                        print(f"Processed {submitted_count} draft submissions. Last record took: {time.time() - record_start:.2f} seconds")
                    
                except Exception as e:
                    error_count += 1
                    frappe.log_error(
                        message=f"Error submitting attendance {attendance_record.name}: {str(e)}",
                        title="Auto Submit Attendance Error"
                    )

        print(f"Time taken for draft submission: {time.time() - draft_submission_start:.2f} seconds")

        # Log summary
        print(
            f"Auto Mark Absent Summary - Date: {today}\n"
            f"Total Active Employees: {len(active_employees)}\n"
            f"Existing Attendance: {len(existing_attendance)}\n"
            f"Marked Absent: {absent_count}\n"
            f"Submitted: {submitted_count}\n"
            f"Errors: {error_count}\n"
            f"Total execution time: {time.time() - start_time:.2f} seconds"
        )

    except Exception as e:
        frappe.log_error(
            message=f"Error in auto mark absent job: {str(e)}",
            title="Auto Mark Absent Job Failed"
        )

def update_historical_attendance_branch_data():
    """
    Updates historical attendance records that are missing custom_branch data.
    Gets branch and other route-related data from the Route doctype if available.
    Uses direct SQL updates to bypass document submission checks and avoid version logs.
    """
    try:
        # Get attendance records without custom_branch but with custom_route
        attendance_records = frappe.db.sql("""
            SELECT name, custom_route
            FROM `tabAttendance`
            WHERE (custom_branch IS NULL OR custom_branch = '')
            AND custom_route IS NOT NULL
            AND custom_route != ''
        """, as_dict=1)

        print(f"Found {len(attendance_records)} attendance records to update")
        
        for idx, attendance in enumerate(attendance_records):
            try:
                # Get route details
                route_details = frappe.db.get_value("Route", 
                    attendance.custom_route,
                    ["branch", "point_name", "area_name", "zone_name"],
                    as_dict=1
                )
                
                if route_details and route_details.branch:
                    # Prepare update fields
                    update_fields = {
                        "custom_branch": route_details.branch
                    }
                    
                    # Add additional route-related fields if they exist in route_details
                    if route_details.point_name:
                        update_fields["custom_route_point"] = route_details.point_name
                    if route_details.area_name:
                        update_fields["custom_area"] = route_details.area_name
                    if route_details.zone_name:
                        update_fields["custom_zone"] = route_details.zone_name
                    
                    # Build SQL SET clause
                    set_clause = ", ".join([f"`{field}` = %s" for field in update_fields.keys()])
                    
                    # Direct SQL update to bypass submission checks and avoid version logs
                    frappe.db.sql(f"""
                        UPDATE `tabAttendance`
                        SET {set_clause}
                        WHERE name = %s
                    """, tuple(list(update_fields.values()) + [attendance.name]))
                    
                    if (idx + 1) % 100 == 0:
                        print(f"Processed {idx + 1} records")
                        frappe.db.commit()
                
            except Exception as e:
                print(f"Error updating attendance {attendance.name}: {str(e)}")
                continue
        
        # Final commit
        frappe.db.commit()
        print("Completed updating historical attendance records")
        
    except Exception as e:
        print(f"Error in update_historical_attendance_branch_data: {str(e)}")
        frappe.log_error(
            message=f"Error updating historical attendance branch data: {str(e)}",
            title="Update Historical Attendance Error"
        )