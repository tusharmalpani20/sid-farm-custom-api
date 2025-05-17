frappe.listview_settings['Salary Slip'] = {
    onload: function (listview) {
        // Check if user has System Manager role
        if (frappe.user_roles.includes('System Manager') || frappe.user == "Administrator" ) {
            // Add button only for System Manager
            listview.page.add_inner_button(__("Process Salary Slips"), function () {
                show_modal_with_buttons(listview);
            })
            .addClass("btn-warning").css({'color':'darkred','font-weight': 'normal'});
        }
    }
};

function show_modal_with_buttons(listview) {
    let d = new frappe.ui.Dialog({
        title: __('Process Salary Slips'),
        size: 'large',
        fields: [
            {
                fieldname: 'message',
                fieldtype: 'HTML',
                options: `
                    <div class="alert alert-info">
                        Please select an option to generate salary slips:
                    </div>
                `
            },
            {
                fieldname: 'current_month_btn',
                fieldtype: 'Button',
                label: __('Generate for Current Month'),
                click: function() {
                    let today = new Date();
                    let year = today.getFullYear();
                    let month = today.getMonth() + 1;
                    process_salary_slips(year, month, d);
                }
            },
            {
                fieldname: 'prev_month_btn',
                fieldtype: 'Button',
                label: __('Generate for Previous Month'),
                click: function() {
                    let today = new Date();
                    let year = today.getFullYear();
                    let month = today.getMonth();
                    if (month === 0) {
                        month = 12;
                        year -= 1;
                    }
                    process_salary_slips(year, month, d);
                }
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            d.hide();
        }
    });

    d.show();
}

function process_salary_slips(year, month, dialog) {
    frappe.dom.freeze(__('Generating Salary Slips...')); // Show loading indicator
    frappe.call({
        method: 'custom_app_api.overrides.doctypes.salary_slip.generate_salary_slips',
        args: { year, month },
        callback: function(r) {
            frappe.dom.unfreeze(); // Hide loading indicator
            if (r.message.success) {
                show_result_dialog(r.message, year, month);
            } else {
                frappe.msgprint(__('Error: {0}', [r.message.message]));
            }
            dialog.hide();
        }
    });
}

function show_result_dialog(result, year, month) {
    let error_html = '';
    let skipped_html = '';
    let monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    let monthText = monthNames[month - 1];

    // Error Table
    if (result.error_details && result.error_details.length > 0) {
        error_html = `
            <div class="alert alert-danger">
                <h4>Errors (${result.error_details.length})</h4>
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Employee ID</th>
                            <th>Employee Name</th>
                            <th>Error</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${result.error_details.map(detail => `
                            <tr>
                                <td>${detail.employee}</td>
                                <td>${detail.employee_name}</td>
                                <td>${detail.error}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    // Skipped Table
    if (result.skipped_details && result.skipped_details.length > 0) {
        skipped_html = `
            <div class="alert alert-warning">
                <h4>Skipped (${result.skipped_details.length})</h4>
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Employee ID</th>
                            <th>Employee Name</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${result.skipped_details.map(detail => `
                            <tr>
                                <td>${detail.employee}</td>
                                <td>${detail.employee_name}</td>
                                <td>${detail.reason}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    // Summary
    let summary_html = `
        <div class="alert alert-info">
            <h4>Summary</h4>
            <ul>
                <li><b>Salary Slips generated for: ${monthText} ${year}</b></li>
                <li>Total Employees: ${result.summary.total_employees}</li>
                <li>Successfully Processed: ${result.summary.success}</li>
                <li>Skipped: ${result.summary.skipped}</li>
                <li>Errors: ${result.summary.errors}</li>
            </ul>
        </div>
    `;

    if (result.csv_url) {
        summary_html += `
            <div class="alert alert-success" style="margin-top: 10px;">
                <a href="${result.csv_url}" target="_blank" download>
                    Download Full CSV Report
                </a>
            </div>
        `;
    }

    let result_dialog = new frappe.ui.Dialog({
        title: __('Salary Slip Generation Results'),
        size: 'large',
        fields: [
            { fieldname: 'summary', fieldtype: 'HTML', options: summary_html },
            { fieldname: 'errors', fieldtype: 'HTML', options: error_html },
            { fieldname: 'skipped', fieldtype: 'HTML', options: skipped_html }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            result_dialog.hide();
        }
    });

    result_dialog.show();
}