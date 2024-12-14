// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on("Additional Salary", {
	custom_pay_in_installment: function(frm) {
		// When checkbox is checked
		if(frm.doc.custom_pay_in_installment) {
			// Set salary_component to "Advance Salary" and make it read-only
			frm.set_value('salary_component', 'Advance Salary');
			frm.set_df_property('salary_component', 'read_only', 1);
		} else {
			// When checkbox is unchecked
			// Make salary_component editable again
			frm.set_df_property('salary_component', 'read_only', 0);
			
			// Reset total amount and number of installments to zero
			frm.set_value('custom_total_amount', 0);
			frm.set_value('custom_number_of_installments', 0);
		}
		
		// Refresh the fields to show changes
		frm.refresh_field('salary_component');
		frm.refresh_field('custom_total_amount');
		frm.refresh_field('custom_number_of_installments');
	},

	custom_number_of_installments: function(frm) {
		if(frm.doc.custom_number_of_installments) {
			// Get first day of next month
			let fromDate = frappe.datetime.add_months(frappe.datetime.month_start(), 1);
			
			// Calculate to_date by adding months to fromDate
			let toDate = frappe.datetime.add_months(fromDate, frm.doc.custom_number_of_installments - 1);

            console.log('From Date:', fromDate);
			console.log('Intermediate toDate:', toDate);
			console.log('Number of installments:', frm.doc.custom_number_of_installments);

			// Get the last day of the final month
			toDate = frappe.datetime.month_end(toDate);

			console.log('Final toDate:', toDate);
			console.log('Number of installments:', frm.doc.custom_number_of_installments);

			// Set the from_date and to_date
			frm.set_value('from_date', fromDate);
			frm.set_value('to_date', toDate);

			// Refresh the fields
			frm.refresh_field('from_date');
			frm.refresh_field('to_date');
		}
	}
});
