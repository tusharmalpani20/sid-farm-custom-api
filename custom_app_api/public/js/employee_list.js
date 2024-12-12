frappe.listview_settings["Employee"] = {
	add_fields: ["status", "branch", "department", "designation", "image", "date_of_joining"],
	filters: [["status", "=", "Active"]],
	get_indicator: function (doc) {
		// Check if employee joined in last 30 days
		const thirtyDaysAgo = frappe.datetime.add_days(frappe.datetime.now_date(), -30);
		const isNewEmployee = doc.date_of_joining >= thirtyDaysAgo;

		// If employee is new, show "New" indicator, otherwise show regular status
		if (isNewEmployee) {
			return ["New", "blue", "date_of_joining,>=," + thirtyDaysAgo];
		}

		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		indicator[1] = { Active: "green", Inactive: "red", Left: "gray", Suspended: "orange" }[doc.status];
		return indicator;
	},
};
