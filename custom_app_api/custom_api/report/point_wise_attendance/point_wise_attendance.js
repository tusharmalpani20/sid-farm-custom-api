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
				let filters = {
					is_active: 1
				};
				
				// Get currently selected zones
				const selectedZones = frappe.query_report.get_filter_value('zones');
				if (selectedZones && selectedZones.length) {
					filters['zone_name'] = ['in', selectedZones];
				}

				return frappe.db.get_list('Point', {
					fields: ['name', 'point_name'],
					filters: filters,
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
		},
		{
			fieldname: "show_designation_wise_breakdown",
			label: __("Show Breakdown by Designation"),
			fieldtype: "Check",
			default: 0,
		}
	]
};
