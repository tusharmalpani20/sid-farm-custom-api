frappe.query_reports["Salary Slip By Employee"] = {
	filters: [
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Select",
			options: getAttendanceYears(),
			default: new Date().getFullYear(),
			reqd: 1
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: [
				{ "value": 1, "label": __("January") },
				{ "value": 2, "label": __("February") },
				{ "value": 3, "label": __("March") },
				{ "value": 4, "label": __("April") },
				{ "value": 5, "label": __("May") },
				{ "value": 6, "label": __("June") },
				{ "value": 7, "label": __("July") },
				{ "value": 8, "label": __("August") },
				{ "value": 9, "label": __("September") },
				{ "value": 10, "label": __("October") },
				{ "value": 11, "label": __("November") },
				{ "value": 12, "label": __("December") }
			].map(m => ({
				value: m.value,
				label: m.label
			})),
			default: new Date().getMonth() + 1,
			reqd: 1
		},
		{
			fieldname: "points",
			label: __("Points"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_list('Point', {
					fields: ['name', 'point_name'],
					filters: {
						is_active: 1
					},
					order_by: 'point_name asc'
				}).then(result => {
					return result.map(r => ({
						value: r.name,
						description: r.point_name
					}));
				});
			}
		},
		{
			fieldname: "include_draft",
			label: __("Include Draft Slips"),
			fieldtype: "Check",
			default: 0
		}
	],
	onload: function(report) {
		// Set year options dynamically
		return frappe.call({
			method: "custom_app_api.custom_app_api.custom_api.report.salary_slip_by_employee.salary_slip_by_employee.get_attendance_years",
			callback: function(r) {
				var year_filter = frappe.query_report.get_filter("year");
				year_filter.df.options = r.message;
				year_filter.df.default = r.message[0]; // First year in the list
				year_filter.refresh();
				year_filter.set_input(year_filter.df.default);
			},
		});
	}
};

// Temporary function until server-side method is called
function getAttendanceYears() {
	const currentYear = new Date().getFullYear();
	const years = [];
	for (let i = currentYear - 2; i <= currentYear + 1; i++) {
		years.push(i.toString());
	}
	return years;
}
