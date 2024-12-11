// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on('Delivery Mapping', {
    refresh: function(frm) {
        
    },
    setup: function(frm) {
        frm.set_query('employee', function() {
            return {
                filters: {
                    'designation': ['in', ['Last Mile Zonal Head', 'Last Mile Lead']],
                    'status': 'Active'
                }
            };
        });
    }
});
