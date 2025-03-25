import frappe
from frappe import _
import time

def check_attendance_index_for_route_tracking() -> None:
    """
    This function is designed to run at 9 o clock every day, this will check for attendance index for route tracking and update the attendance index
    """
    try:
        attendance_index_check_start = time.time()

        output = frappe.db.sql("""
                            CREATE INDEX IF NOT EXISTS idx_route_tracking_attendance   ON `tabRoute Tracking` (attendance) ALGORITHM=INPLACE;
                        """, as_dict=1)

        print(output)

        attendance_index_check_end = time.time()

        print(f"Time taken to check attendance index: {attendance_index_check_end - attendance_index_check_start:.2f} seconds")

    except Exception as e:
        frappe.log_error(
            message=f"Error in checking attendance index: {str(e)}",
            title="Check Attendance Index Failed"
        )