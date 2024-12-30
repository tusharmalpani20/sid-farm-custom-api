frappe.ui.form.on('Backup Delivery Partner Mapping', {
    refresh: function(frm) {
        frm.add_custom_button(__('Get Backup Delivery Partners'), function() {
            frm.call({
                doc: frm.doc,
                method: 'get_backup_delivery_partners',
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        render_employees_table(frm, r.message);
                    } else {
                        frappe.msgprint(__('No Backup Delivery Partners found'));
                    }
                }
            });
        });
    },

    before_submit: function(frm) {
        let employees_wrapper = frm.fields_dict.employees_html.$wrapper;
        let rows = employees_wrapper.find('tr[data-employee]');
        let employees_data = [];
        
        rows.each(function() {
            let $row = $(this);
            let route = $row.find('.route-select').val();
            
            if (route) {
                employees_data.push({
                    employee: $row.attr('data-employee'),
                    route: route,
                    point: $row.find('.point-select').val(),
                    area: $row.find('.area-select').val(),
                    zone: $row.find('.zone-select').val()
                });
            }
        });
        
        frm.doc.employees_data = JSON.stringify(employees_data);
    }
});

function render_employees_table(frm, employees) {
    let wrapper = frm.fields_dict.employees_html.$wrapper;
    wrapper.empty();

    frappe.db.get_list('Route', {
        fields: ['name'],
        limit: 0
    }).then(routes => {
        let table = $(`
            <div class="table-responsive">
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Employee ID</th>
                            <th>Employee Name</th>
                            <th>Route</th>
                            <th>Point</th>
                            <th>Area</th>
                            <th>Zone</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${employees.map(emp => `
                            <tr data-employee="${emp.name}">
                                <td>${emp.name || ''}</td>
                                <td>${emp.employee_name || ''}</td>
                                <td>
                                    <select class="form-control route-select">
                                        <option value="">Select Route</option>
                                        ${routes.map(route => `
                                            <option value="${route.name}" 
                                                ${emp.custom_route === route.name ? 'selected' : ''}>
                                                ${route.name}
                                            </option>
                                        `).join('')}
                                    </select>
                                </td>
                                <td><input type="text" class="form-control point-select" value="${emp.custom_point || ''}" readonly></td>
                                <td><input type="text" class="form-control area-select" value="${emp.custom_area || ''}" readonly></td>
                                <td><input type="text" class="form-control zone-select" value="${emp.custom_zone || ''}" readonly></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `);
        
        wrapper.html(table);

        wrapper.find('.route-select').each(function() {
            $(this).select2({
                placeholder: 'Select Route',
                allowClear: true
            }).on('change', function() {
                let $row = $(this).closest('tr');
                let route = $(this).val();

                if (route) {
                    frappe.call({
                        method: 'frappe.client.get_value',
                        args: {
                            doctype: 'Route',
                            filters: { name: route },
                            fieldname: ['point_name', 'area_name', 'zone_name']
                        },
                        callback: function(r) {
                            if (r.message) {
                                $row.find('.point-select').val(r.message.point_name);
                                $row.find('.area-select').val(r.message.area_name);
                                $row.find('.zone-select').val(r.message.zone_name);
                            }
                        }
                    });
                }
            });
        });
    });
}