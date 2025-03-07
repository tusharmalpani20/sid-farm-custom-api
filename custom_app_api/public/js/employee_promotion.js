// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Promotion", {
	setup: function(frm) {
		frm.set_query("promotion_date", function() {
			return {
				filters: {
				}
			};
		});
	},
	
	refresh: function(frm) {
	},
	
	promotion_date: function(frm) {
		if (frm.doc.promotion_date < frappe.datetime.get_today()) {
			frappe.msgprint(__("Promotion date cannot be in the past. Please select today or a future date."));
			frm.set_value("promotion_date", frappe.datetime.get_today());
		}
	},
	
	before_save: function(frm) {
		if (frm.doc.promotion_date < frappe.datetime.get_today()) {
			frappe.throw(__("Promotion date cannot be in the past. Please select today or a future date."));
			return false;
		}
	}
});
