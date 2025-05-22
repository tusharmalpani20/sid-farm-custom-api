frappe.query_reports["Leave Policy Assignment Status"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
		},
		{
			fieldname: "show_only_without_assignment",
			label: __("Show Only Employees Without Assignment"),
			fieldtype: "Check",
			default: 0
		}
	]
};
