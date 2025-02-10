// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on("BMC", {
	refresh(frm) {

	},

	state: function(frm) {
		// Clear mandal_list when state changes
		frm.set_value('mandal_list', []);
		
		// Set filters for mandal_list based on selected state
		frm.set_query('mandal_list', function() {
			return {
				filters: {
					state: frm.doc.state
				}
			};
		});
	}
});
