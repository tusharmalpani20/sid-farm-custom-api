// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh: function(frm) {
		console.log('Employee form refresh triggered');
		
		// Skip for admin and system users
		if (frappe.user.has_role('Administrator') || frappe.user.has_role('System Manager')) {
			console.log('User is Admin/System Manager - skipping restrictions');
			return;
		}

		// Get current user's employee record
		console.log('Fetching employee record for user:', frappe.session.user);
		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Employee',
				filters: { user_id: frappe.session.user },
				fieldname: ['designation', 'name']
			},
			callback: function(r) {
				if (!r.message) {
					console.log('No employee record found for current user');
					return;
				}

				const userDesignation = r.message.designation;
				console.log('User designation:', userDesignation);
				
				// Set filters and permissions based on user role
				if (userDesignation === 'Last Mile Lead') {
					console.log('Applying Last Mile Lead restrictions');
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
					console.log('Applying Last Mile Zonal Head restrictions');
					// frm.set_value('reports_to', r.message.name);
					frm.set_query('designation', function() {
						return {
							filters: [
								['designation_name', 'not in', ['Last Mile Zonal Head', 'Last Mile Head']]
							]
						};
					});
				}
				else if (userDesignation === 'Last Mile Head') {
					console.log('Applying Last Mile Head restrictions');
					// frm.set_value('reports_to', r.message.name);
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

	custom_is_notice_period: function(frm) {
		if (!frm.doc.custom_is_notice_period) {
			frappe.db.get_list('Employee Separation', {
				filters: {
					'employee': frm.doc.name,
					'docstatus': ['!=', 2]  // Not cancelled
				}
			}).then(separations => {
				if (separations && separations.length > 0) {
					// Reset the value back to true
					frm.set_value('custom_is_notice_period', 1);
					
					frappe.throw(__(`
						Cannot remove notice period status. 
						Please delete or cancel existing Employee Separation records first.
					`));
				}
			});
		}
	}
});
