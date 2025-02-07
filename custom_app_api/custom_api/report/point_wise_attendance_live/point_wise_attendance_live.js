frappe.query_reports["Point Wise Attendance Live"] = {
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
		}
	],
	
	onload: function(report) {
		// Set up auto-refresh interval
		report.page.add_inner_button(__('Auto Refresh'), function() {
			if (!report.auto_refresh_interval) {
				console.log('Starting auto-refresh...');
				// Start auto-refresh
				report.auto_refresh_interval = setInterval(() => {
					console.log('Auto-refresh triggered at:', new Date().toLocaleTimeString());
					report.refresh();
				}, 60000); // 60000 ms = 1 minute
				
				// Change button label
				report.page.inner_toolbar.find('.btn:contains("Auto Refresh")').text(__('Stop Auto Refresh'));
				frappe.show_alert({
					message: __('Auto-refresh enabled - refreshing every minute'),
					indicator: 'green'
				}, 3);
			} else {
				console.log('Stopping auto-refresh...');
				// Stop auto-refresh
				clearInterval(report.auto_refresh_interval);
				report.auto_refresh_interval = null;
				
				// Reset button label
				report.page.inner_toolbar.find('.btn:contains("Stop Auto Refresh")').text(__('Auto Refresh'));
				frappe.show_alert({
					message: __('Auto-refresh disabled'),
					indicator: 'orange'
				}, 3);
			}
		});
	},

	onclose: function(report) {
		// Clean up interval when report is closed
		if (report.auto_refresh_interval) {
			console.log('Cleaning up auto-refresh on report close');
			clearInterval(report.auto_refresh_interval);
			report.auto_refresh_interval = null;
		}
	}
};
