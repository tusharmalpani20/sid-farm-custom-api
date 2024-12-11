// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh: function(frm) {
		// Skip for admin and system users
		if (frappe.user.has_role('Administrator') || frappe.user.has_role('System Manager')) {
			return;
		}

		// Get current user's employee record
		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Employee',
				filters: { user_id: frappe.session.user },
				fieldname: ['designation', 'name']
			},
			callback: function(r) {
				if (!r.message) {
					return;
				}

				const userDesignation = r.message.designation;
				
				// Set filters and permissions based on user role
				if (userDesignation === 'Last Mile Lead') {
					frm.set_value('reports_to', r.message.name);
					frm.set_df_property('reports_to', 'read_only', 1);
					frm.set_query('designation', function() {
						return {
							filters: [
								['designation_name', 'not in', ['Last Mile Lead', 'Last Mile Zonal Head', 'Last Mile Head']]
							]
						};
					});
				}
				else if (userDesignation === 'Last Mile Zonal Head') {
					frm.set_value('reports_to', r.message.name);
					frm.set_query('designation', function() {
						return {
							filters: [
								['designation_name', 'not in', ['Last Mile Zonal Head', 'Last Mile Head']]
							]
						};
					});
				}
				else if (userDesignation === 'Last Mile Head') {
					frm.set_value('reports_to', r.message.name);
					frm.set_query('designation', function() {
						return {
							filters: [
								['designation_name', 'not in', ['Last Mile Head']]
							]
						};
					});
				}
			}
		});
	},
});
