frappe.query_reports["Point Wise Attendance"] = {
	filters: [
		{
			fieldname: "date",
			label: __("Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "points",
			label: __("Points"),
			fieldtype: "MultiSelectList",
			get_data: function() {
				return frappe.db.get_list('Employee', {
					fields: ['custom_point'],
					filters: {
						custom_point: ['is', 'set']
					},
					group_by: 'custom_point',
					order_by: 'custom_point asc'
				}).then(result => {
					return result.map(r => r.custom_point);
				});
			}
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "include_company_descendants",
			label: __("Include Company Descendants"),
			fieldtype: "Check",
			default: 1,
		}
	]
};
