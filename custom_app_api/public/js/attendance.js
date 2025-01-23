// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attendance", {
	refresh: function(frm) {
		if (frm.doc.name) {
			// Fetch route tracking data for this attendance
			frappe.call({
				method: 'custom_app_api.custom_api.api_end_points.record_geo_location_api.get_unique_route_tracking',
				args: {
					attendance: frm.doc.name
				},
				callback: function(response) {
					if (response.message && response.message.length > 0) {
						// Convert the response to coordinates array
						const coords = response.message.map(point => [point.latitude, point.longitude]);
						
						// Get the map instance
						let map = frm.fields_dict.custom_location_path.map;
						
						// Create and add the polyline
						let polyline = L.polyline(coords, {
							color: "red",
							weight: 3,
							opacity: 0.7
						}).addTo(map);

						// Calculate total distance
						let totalDistance = 0;
						for(let i = 0; i < coords.length - 1; i++) {
							let point1 = L.latLng(coords[i]);
							let point2 = L.latLng(coords[i + 1]);
							totalDistance += point1.distanceTo(point2);
						}
						
						// Convert distance to kilometers and round to 2 decimal places
						let distanceInKm = (totalDistance / 1000).toFixed(2);
						
						// Add distance info to the map
						L.control.attribution({
							prefix: `Total Distance: ${distanceInKm} km`
						}).addTo(map);
						
						// Fit the map to show the entire route
						map.fitBounds(polyline.getBounds());

						// Add markers for start and end points if there are coordinates
						if (coords.length > 0) {
							// Start point - green marker
							L.marker(coords[0], {
								icon: L.divIcon({
									className: 'custom-div-icon',
									html: `<div style='background-color: #4CAF50; padding: 5px; border-radius: 50%;' 
											title='Start Point'></div>`,
									iconSize: [15, 15]
								})
							}).addTo(map);

							// End point - red marker
							L.marker(coords[coords.length - 1], {
								icon: L.divIcon({
									className: 'custom-div-icon',
									html: `<div style='background-color: #f44336; padding: 5px; border-radius: 50%;' 
											title='End Point'></div>`,
									iconSize: [15, 15]
								})
							}).addTo(map);
						}
					}
				}
			});
		}
	}
});
