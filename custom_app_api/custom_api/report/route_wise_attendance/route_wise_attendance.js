// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.query_reports["Route Wise Attendance"] = {
	filters: [
		{
			fieldname: "date_range",
			label: __("Date Range Type"),
			fieldtype: "Select",
			options: ["Daily", "Monthly", "Quarterly"],
			default: "Monthly",
			reqd: 1,
			on_change: function(report) {
				let date_range = frappe.query_report.get_filter_value('date_range');
				let date_filters = ['specific_date', 'month', 'year', 'quarter'];
				
				// First hide all date-related filters
				date_filters.forEach(filter => {
					let filterObj = frappe.query_report.get_filter(filter);
					if (filterObj) {
						filterObj.df.hidden = 1;
						filterObj.df.reqd = 0;
					}
				});
				
				// Then show and set required for relevant filters
				if (date_range === 'Daily') {
					let specific_date = frappe.query_report.get_filter('specific_date');
					if (specific_date) {
						specific_date.df.hidden = 0;
						specific_date.df.reqd = 1;
					}
				} else if (date_range === 'Monthly') {
					let month = frappe.query_report.get_filter('month');
					let year = frappe.query_report.get_filter('year');
					if (month) {
						month.df.hidden = 0;
						month.df.reqd = 1;
					}
					if (year) {
						year.df.hidden = 0;
						year.df.reqd = 1;
					}
				} else if (date_range === 'Quarterly') {
					let quarter = frappe.query_report.get_filter('quarter');
					let year = frappe.query_report.get_filter('year');
					if (quarter) {
						quarter.df.hidden = 0;
						quarter.df.reqd = 1;
					}
					if (year) {
						year.df.hidden = 0;
						year.df.reqd = 1;
					}
				}
				
				// Refresh all filters to apply changes
				date_filters.forEach(filter => {
					let filterObj = frappe.query_report.get_filter(filter);
					if (filterObj) filterObj.refresh();
				});
			}
		},
		{
			fieldname: "specific_date",
			label: __("Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			hidden: 1,
			reqd: 0
		},
		{
			fieldname: "quarter",
			label: __("Quarter"),
			fieldtype: "Select",
			options: [
				"Q1 (Jan-Mar)",
				"Q2 (Apr-Jun)", 
				"Q3 (Jul-Sep)",
				"Q4 (Oct-Dec)"
			],
			default: "Q1 (Jan-Mar)",
			hidden: 1,
			reqd: 0
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: [
				{ "value": 1, "label": __("Jan") },
				{ "value": 2, "label": __("Feb") },
				{ "value": 3, "label": __("Mar") },
				{ "value": 4, "label": __("Apr") },
				{ "value": 5, "label": __("May") },
				{ "value": 6, "label": __("Jun") },
				{ "value": 7, "label": __("Jul") },
				{ "value": 8, "label": __("Aug") },
				{ "value": 9, "label": __("Sep") },
				{ "value": 10, "label": __("Oct") },
				{ "value": 11, "label": __("Nov") },
				{ "value": 12, "label": __("Dec") },
			],
			default: frappe.datetime.str_to_obj(frappe.datetime.get_today()).getMonth() + 1,
			hidden: 0,
			reqd: 1
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Select",
			default: frappe.datetime.get_today().split("-")[0],
			hidden: 0,
			reqd: 1
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			get_query: () => {
				var company = frappe.query_report.get_filter_value("company");
				return {
					filters: {
						company: company,
					},
				};
			},
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
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: ["", "Branch", "Grade", "Department", "Designation", "Route", "Area", "Zone", "Point"],
			default: "Route",
		},
		{
			fieldname: "include_company_descendants",
			label: __("Include Company Descendants"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "summarized_view",
			label: __("Summarized View"),
			fieldtype: "Check",
			default: 0,
		},
	],
	onload: function(report) {
		// Set year options
		return frappe.call({
			method: "hrms.hr.report.monthly_attendance_sheet.monthly_attendance_sheet.get_attendance_years",
			callback: function(r) {
				var year_filter = frappe.query_report.get_filter("year");
				year_filter.df.options = r.message;
				year_filter.df.default = r.message.split("\n")[0];
				year_filter.refresh();
				year_filter.set_input(year_filter.df.default);
				
				// Trigger the date_range filter to set up initial visibility
				frappe.query_report.get_filter('date_range').trigger_change();
			},
		});
	},
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		const summarized_view = frappe.query_report.get_filter_value("summarized_view");
		const group_by = frappe.query_report.get_filter_value("group_by");

		if (group_by && column.colIndex === 1) {
			value = "<strong>" + value + "</strong>";
		}

		if (!summarized_view) {
			if ((group_by && column.colIndex > 3) || (!group_by && column.colIndex > 2)) {
				if (value == "P" || value == "WFH")
					value = "<span style='color:green'>" + value + "</span>";
				else if (value == "A") value = "<span style='color:red'>" + value + "</span>";
				else if (value == "HD") value = "<span style='color:orange'>" + value + "</span>";
				else if (value == "L") value = "<span style='color:#318AD8'>" + value + "</span>";
			}
		}

		return value;
	},
	onchange: function(report) {
		let group_by = frappe.query_report.get_filter_value('group_by');
		let summarized_view = frappe.query_report.get_filter('summarized_view');
		
		// Auto-set and disable summarized view for Route/Area/Zone/Point
		if (['Route', 'Area', 'Zone', 'Point'].includes(group_by)) {
			summarized_view.set_value(1);
			summarized_view.df.read_only = 1;
		} else {
			summarized_view.df.read_only = 0;
		}
		summarized_view.refresh();
	},
};
