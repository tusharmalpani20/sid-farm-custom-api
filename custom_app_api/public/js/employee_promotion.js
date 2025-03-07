// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Promotion", {
	setup: function(frm) {
		console.log("Setup function called");
		frm.set_query("promotion_date", function() {
			console.log("set_query executed for promotion_date");
			return {
				filters: {
				}
			};
		});
	},
	
	refresh: function(frm) {
		console.log("Form refreshed - Script loaded successfully");
		console.log("Current promotion date:", frm.doc.promotion_date);
	},
	
	promotion_date: function(frm) {
		console.log("Promotion date changed to:", frm.doc.promotion_date);
		console.log("Today's date:", frappe.datetime.get_today());
		
		if (frm.doc.promotion_date < frappe.datetime.get_today()) {
			console.log("Invalid date detected - showing message");
			frappe.msgprint(__("Promotion date cannot be in the past. Please select today or a future date."));
			frm.set_value("promotion_date", frappe.datetime.get_today());
		}
	},
	
	before_save: function(frm) {
		console.log("Before save triggered");
		console.log("Checking date:", frm.doc.promotion_date);
		
		if (frm.doc.promotion_date < frappe.datetime.get_today()) {
			console.log("Invalid date detected - throwing error");
			frappe.throw(__("Promotion date cannot be in the past. Please select today or a future date."));
			return false;
		}
	}
});
