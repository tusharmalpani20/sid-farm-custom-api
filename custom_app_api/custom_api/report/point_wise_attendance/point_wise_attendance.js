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
			fieldname: "zones",
			label: __("Zones"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_list('Zone', {
					fields: ['name', 'zone_name'],
					filters: {
						is_active: 1
					},
					order_by: 'zone_name asc'
				}).then(result => {
					return result.map(r => ({
						value: r.name,
						description: r.zone_name
					}));
				});
			}
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
