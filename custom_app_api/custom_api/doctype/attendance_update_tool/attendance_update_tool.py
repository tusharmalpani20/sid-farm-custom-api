# Copyright (c) 2025, Hopnet and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class AttendanceUpdateTool(Document):
	def on_submit(self):
		try:
			# Find existing attendance record
			attendance = frappe.db.get_value(
				"Attendance",
				{
					"employee": self.employee,
					"attendance_date": getdate(self.date),
					"docstatus": ["!=", 2]  # Not cancelled
				},
				"name"
			)

			if not attendance:
				frappe.throw(f"No attendance record found for employee {self.employee} on {self.date}")

			# Update the attendance status directly using db_set
			frappe.db.set_value(
				"Attendance",
				attendance,
				"status",
				self.status,
				update_modified=True
			)

			frappe.db.commit()
			
			frappe.msgprint(f"Successfully updated attendance status to {self.status}")

		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(
				message=f"Error updating attendance status: {str(e)}\n{frappe.get_traceback()}",
				title="Attendance Update Error"
			)
			frappe.throw(f"Failed to update attendance: {str(e)}")
