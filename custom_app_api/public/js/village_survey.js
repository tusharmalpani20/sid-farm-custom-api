// Copyright (c) 2024, Hopnet and contributors
// For license information, please see license.txt

frappe.ui.form.on("Village Survey", {
	refresh: function(frm) {
		// Only proceed if we have coordinates
		if (!frm.doc.latitude || !frm.doc.longitude) return;

		// Get the map instance
		let map = frm.fields_dict.map.map;
		
		// Clear any existing markers
		if (frm.marker) {
			map.removeLayer(frm.marker);
		}

		// Create marker options with a custom icon
		const markerOptions = {
			icon: L.divIcon({
				iconSize: [50, 50],
				iconAnchor: [25, 59],
				className: 'tracking-marker',
				html: '📍' // Using a pin emoji, but you can customize this
			})
		};

		// Add the marker to the map
		frm.marker = L.marker(
			[frm.doc.latitude, frm.doc.longitude], 
			markerOptions
		).addTo(map);

		// Add a popup with location info
		frm.marker.bindPopup(`
			<b>Location Details:</b><br>
			Latitude: ${frm.doc.latitude}<br>
			Longitude: ${frm.doc.longitude}<br>
			Accuracy: ${frm.doc.accuracy} meters<br>
			Recorded: ${frm.doc.recorded_at}
		`)
        // .openPopup();

		// Center the map on the marker
		map.setView([frm.doc.latitude, frm.doc.longitude], 15);

		// Add custom CSS for the marker
		if (!document.getElementById('tracking-marker-style')) {
			const style = document.createElement('style');
			style.id = 'tracking-marker-style';
			style.textContent = `
				.tracking-marker {
					font-size: 50px;
					text-align: center;
				}
			`;
			document.head.appendChild(style);
		}
	}
});
