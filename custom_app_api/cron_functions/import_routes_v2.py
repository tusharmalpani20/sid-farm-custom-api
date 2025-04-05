import frappe
import requests
from datetime import datetime

def import_routes_v2():
    """
    Daily cron job to import routes from analytics API with complete hierarchy.
    This function imports city, zone, area, point, and route based on the updated schema.
    Runs at the end of each day.
    """
    try:
        print(f"Starting route import v2 at {datetime.now()}")
        
        # Fetch data from API
        api_url = frappe.conf.get('analytics_api_url_for_routes_v2')
        api_key = frappe.conf.get('analytics_api_key_v2')
        
        if not api_url or not api_key:
            frappe.throw("Analytics API configuration missing in site config")
        
        print("Fetching data from analytics API...")
        response = requests.get(api_url, params={"api_key": api_key})
        
        if response.status_code != 200:
            frappe.throw(f"API request failed with status code: {response.status_code}")
        
        data = response.json()
        rows = data["query_result"]["data"]["rows"]
        print(f"Retrieved {len(rows)} routes from API")

        # Create maps for existing records
        city_sf_analytics_id_map = {}
        zone_sf_analytics_id_map = {}
        area_sf_analytics_id_map = {}
        point_sf_analytics_id_map = {}
        route_sf_analytics_id_map = {}
        
        # Get existing records from Frappe
        cities = frappe.get_all("City", fields=["name", "city_name", "sf_analytics_id"], limit_page_length=None)
        for city in cities:
            if city.sf_analytics_id:
                city_sf_analytics_id_map[city.sf_analytics_id] = {
                    "name": city.name,
                    "city_name": city.city_name
                }
        
        zones = frappe.get_all("Zone", fields=["name", "zone_name", "sf_analytics_id"], limit_page_length=None)
        for zone in zones:
            if zone.sf_analytics_id:
                zone_sf_analytics_id_map[zone.sf_analytics_id] = {
                    "name": zone.name,
                    "zone_name": zone.zone_name
                }
        
        areas = frappe.get_all("Area", fields=["name", "area_name", "sf_analytics_id"], limit_page_length=None)
        for area in areas:
            if area.sf_analytics_id:
                area_sf_analytics_id_map[area.sf_analytics_id] = {
                    "name": area.name,
                    "area_name": area.area_name
                }
        
        points = frappe.get_all("Point", fields=["name", "point_name", "sf_analytics_id"], limit_page_length=None)
        for point in points:
            if point.sf_analytics_id:
                point_sf_analytics_id_map[point.sf_analytics_id] = {
                    "name": point.name,
                    "point_name": point.point_name
                }
        
        routes = frappe.get_all("Route", fields=["name", "route_name", "sf_analytics_id"], limit_page_length=None)
        for route in routes:
            if route.sf_analytics_id:
                route_sf_analytics_id_map[route.sf_analytics_id] = {
                    "name": route.name,
                    "route_name": route.route_name
                }
        
        print(f"Found {len(city_sf_analytics_id_map)} existing cities in system")
        print(f"Found {len(zone_sf_analytics_id_map)} existing zones in system")
        print(f"Found {len(area_sf_analytics_id_map)} existing areas in system")
        print(f"Found {len(point_sf_analytics_id_map)} existing points in system")
        print(f"Found {len(route_sf_analytics_id_map)} existing routes in system")
        
        # Process each row
        new_cities_count = 0
        new_zones_count = 0
        new_areas_count = 0
        new_points_count = 0
        new_routes_count = 0
        
        # Start transaction
        frappe.db.begin()
        
        try:
            for row in rows:
                try:
                    # Determine state and branch based on city
                    state_name = None
                    branch = None
                    
                    if row["city"] == "BLR":
                        state_name = "Karnataka"
                        branch = "Bengaluru"
                    elif row["city"] == "HYD":
                        state_name = "Telangana"
                        branch = "Hyderabad"
                    else:
                        print(f"Unknown city code: {row['city']}, skipping row")
                        continue
                    
                    # # Get or create state
                    # state_doc = None
                    # if frappe.db.exists("State", {"state_name": state_name}):
                    #     state_doc = frappe.get_doc("State", {"state_name": state_name})
                    # else:
                    #     state_doc = frappe.get_doc({
                    #         "doctype": "State",
                    #         "state_name": state_name
                    #     })
                    #     state_doc.insert()

                    state_doc = {
                        "name": state_name,
                        "state_name": state_name
                    }
                    
                    # Get or create city
                    city_doc = None
                    if row["city_id"] in city_sf_analytics_id_map:
                        # We already have the city in our map, no need to fetch it again
                        city_name = city_sf_analytics_id_map[row["city_id"]]["name"]
                    else:
                        city_doc = frappe.get_doc({
                            "doctype": "City",
                            "city_name": row["city"],
                            "state_name": state_doc.name,
                            "sf_analytics_id": row["city_id"]
                        })
                        city_doc.insert()
                        
                        # Add to map
                        city_name = city_doc.name
                        city_sf_analytics_id_map[row["city_id"]] = {
                            "name": city_name,
                            "city_name": city_doc.city_name
                        }
                        new_cities_count += 1
                    
                    # Get or create zone
                    zone_doc = None
                    if row["zone_id"] in zone_sf_analytics_id_map:
                        # We already have the zone in our map, no need to fetch it again
                        zone_name = zone_sf_analytics_id_map[row["zone_id"]]["name"]
                    else:
                        zone_doc = frappe.get_doc({
                            "doctype": "Zone",
                            "zone_name": row["zone"],
                            "city_name": city_name,
                            "state_name": state_doc.name,
                            "branch": branch,
                            "sf_analytics_id": row["zone_id"]
                        })
                        zone_doc.insert()
                        
                        # Add to map
                        zone_name = zone_doc.name
                        zone_sf_analytics_id_map[row["zone_id"]] = {
                            "name": zone_name,
                            "zone_name": zone_doc.zone_name
                        }
                        new_zones_count += 1
                    
                    # Get or create area
                    area_doc = None
                    if row["area_id"] in area_sf_analytics_id_map:
                        # We already have the area in our map, no need to fetch it again
                        area_name = area_sf_analytics_id_map[row["area_id"]]["name"]
                    else:
                        area_doc = frappe.get_doc({
                            "doctype": "Area",
                            "area_name": row["area"],
                            "zone_name": zone_name,
                            "city_name": city_name,
                            "state_name": state_doc.name,
                            "branch": branch,
                            "sf_analytics_id": row["area_id"]
                        })
                        area_doc.insert()
                        
                        # Add to map
                        area_name = area_doc.name
                        area_sf_analytics_id_map[row["area_id"]] = {
                            "name": area_name,
                            "area_name": area_doc.area_name
                        }
                        new_areas_count += 1
                    
                    # Get or create point
                    point_doc = None
                    if row["pickup_point_id"] in point_sf_analytics_id_map:
                        # We already have the point in our map, no need to fetch it again
                        point_name = point_sf_analytics_id_map[row["pickup_point_id"]]["name"]
                    else:
                        point_doc = frappe.get_doc({
                            "doctype": "Point",
                            "point_name": row["pick_up_point"],
                            "point_code": str(row["pickup_point_id"]),
                            "area_name": area_name,
                            "zone_name": zone_name,
                            "city_name": city_name,
                            "state_name": state_doc.name,
                            "branch": branch,
                            "sf_analytics_id": row["pickup_point_id"]
                        })
                        point_doc.insert()
                        
                        # Add to map
                        point_name = point_doc.name
                        point_sf_analytics_id_map[row["pickup_point_id"]] = {
                            "name": point_name,
                            "point_name": point_doc.point_name
                        }
                        new_points_count += 1
                    
                    # Get or create route
                    if row["route_id"] in route_sf_analytics_id_map:
                        # Update existing route's total_delivery
                        route_name = route_sf_analytics_id_map[row["route_id"]]["name"]
                        route_doc = frappe.get_doc("Route", route_name)
                        route_doc.total_delivery = row["count_of_customers"]
                        route_doc.save()
                    else:
                        route_doc = frappe.get_doc({
                            "doctype": "Route",
                            "route_name": row["route"],
                            "point_name": point_name,
                            "area_name": area_name,
                            "zone_name": zone_name,
                            "city_name": city_name,
                            "state_name": state_doc.name,
                            "branch": branch,
                            "total_delivery": row["count_of_customers"],
                            "sf_analytics_id": row["route_id"]
                        })
                        route_doc.insert()
                        
                        # Add to map
                        route_name = route_doc.name
                        route_sf_analytics_id_map[row["route_id"]] = {
                            "name": route_name,
                            "route_name": route_doc.route_name
                        }
                        new_routes_count += 1
                
                except Exception as e:
                    print(f"Error processing row {row}: {str(e)}")
                    frappe.db.rollback()
                    continue
            
            # Commit transaction once at the end
            frappe.db.commit()
            
            # Log summary
            summary = f"""
Route import v2 completed:
- Total rows processed: {len(rows)}
- New cities created: {new_cities_count}
- New zones created: {new_zones_count}
- New areas created: {new_areas_count}
- New points created: {new_points_count}
- New routes created: {new_routes_count}
- Timestamp: {datetime.now()}
"""
            print(summary)
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"Route import v2 failed during processing: {str(e)}"
            print(error_msg)
            frappe.log_error(title="Route Import v2 Failed", message=error_msg)
            raise

    except Exception as e:
        error_msg = f"Route import v2 failed: {str(e)}"
        print(error_msg)
        frappe.log_error(title="Route Import v2 Failed", message=error_msg)
        raise 

def map_old_entries():
    """
    Function to map old entries with their new sf_analytics_id values.
    This function updates existing city, zone, area, point, and route records
    with their corresponding sf_analytics_id values from the analytics API.
    """
    try:
        print(f"Starting mapping of old entries at {datetime.now()}")
        
        # Fetch data from API
        api_url = frappe.conf.get('analytics_api_url_for_routes_v2')
        api_key = frappe.conf.get('analytics_api_key_v2')
        
        if not api_url or not api_key:
            frappe.throw("Analytics API configuration missing in site config")
        
        print("Fetching data from analytics API...")
        response = requests.get(api_url, params={"api_key": api_key})
        
        if response.status_code != 200:
            frappe.throw(f"API request failed with status code: {response.status_code}")
        
        data = response.json()
        rows = data["query_result"]["data"]["rows"]
        print(f"Retrieved {len(rows)} routes from API")
        
        # Create maps for city, zone, area, point, and route
        city_map = {}  # city_name -> city_id
        zone_map = {}  # zone_name-branch -> zone_id
        area_map = {}  # area_name-branch -> area_id
        point_map = {}  # point_name-branch -> point_id
        route_map = {}  # route_name-branch -> route_id
        
        # Populate maps from rows
        for row in rows:
            # Determine branch based on city
            branch = None
            if row["city"] == "BLR":
                branch = "Bengaluru"
            elif row["city"] == "HYD":
                branch = "Hyderabad"
            else:
                print(f"Unknown city code: {row['city']}, skipping row")
                continue
            
            # Add to city map
            city_map[row["city"]] = row["city_id"]
            
            # Add to zone map
            zone_key = f"{row['zone']}-{branch}"
            zone_map[zone_key] = row["zone_id"]
            
            # Add to area map
            area_key = f"{row['area']}-{branch}"
            area_map[area_key] = row["area_id"]
            
            # Add to point map
            point_key = f"{row['pick_up_point']}-{branch}"
            point_map[point_key] = row["pickup_point_id"]
            
            # Add to route map
            route_key = f"{row['route']}-{branch}"
            route_map[route_key] = row["route_id"]
        
        print(f"Created maps with {len(city_map)} cities, {len(zone_map)} zones, {len(area_map)} areas, {len(point_map)} points, and {len(route_map)} routes")
        
        # Start transaction
        frappe.db.begin()
        
        try:
            # Update cities
            updated_cities = 0
            cities = frappe.get_all("City", fields=["name", "city_name", "sf_analytics_id"], limit_page_length=None)
            for city in cities:
                if not city.sf_analytics_id and city.city_name in city_map:
                    try:
                        city_doc = frappe.get_doc("City", city.name)
                        city_doc.sf_analytics_id = city_map[city.city_name]
                        city_doc.save()
                        updated_cities += 1
                        print(f"Updated city: {city.city_name} with sf_analytics_id: {city_map[city.city_name]}")
                    except Exception as e:
                        print(f"Error updating city {city.city_name}: {str(e)}")
            
            # Update zones
            updated_zones = 0
            zones = frappe.get_all("Zone", fields=["name", "zone_name", "branch", "sf_analytics_id"], limit_page_length=None)
            for zone in zones:
                zone_key = zone.name
                if not zone.sf_analytics_id and zone_key in zone_map:
                    try:
                        zone_doc = frappe.get_doc("Zone", zone.name)
                        zone_doc.sf_analytics_id = zone_map[zone_key]
                        zone_doc.save()
                        updated_zones += 1
                        print(f"Updated zone: {zone_key} with sf_analytics_id: {zone_map[zone_key]}")
                    except Exception as e:
                        print(f"Error updating zone {zone_key}: {str(e)}")
            
            # Update areas
            updated_areas = 0
            areas = frappe.get_all("Area", fields=["name", "area_name", "branch", "sf_analytics_id"], limit_page_length=None)
            for area in areas:
                area_key = area.name
                if not area.sf_analytics_id and area_key in area_map:
                    try:
                        area_doc = frappe.get_doc("Area", area.name)
                        area_doc.sf_analytics_id = area_map[area_key]
                        area_doc.save()
                        updated_areas += 1
                        print(f"Updated area: {area_key} with sf_analytics_id: {area_map[area_key]}")
                    except Exception as e:
                        print(f"Error updating area {area_key}: {str(e)}")
            
            # Update points
            updated_points = 0
            points = frappe.get_all("Point", fields=["name", "point_name", "branch", "sf_analytics_id"], limit_page_length=None)
            for point in points:
                point_key = point.name
                if not point.sf_analytics_id and point_key in point_map:
                    try:
                        point_doc = frappe.get_doc("Point", point.name)
                        point_doc.sf_analytics_id = point_map[point_key]
                        point_doc.save()
                        updated_points += 1
                        print(f"Updated point: {point_key} with sf_analytics_id: {point_map[point_key]}")
                    except Exception as e:
                        print(f"Error updating point {point_key}: {str(e)}")
            
            # Update routes
            updated_routes = 0
            routes = frappe.get_all("Route", fields=["name", "route_name", "branch", "sf_analytics_id"], limit_page_length=None)
            for route in routes:
                route_key = route.name
                if not route.sf_analytics_id and route_key in route_map:
                    try:
                        route_doc = frappe.get_doc("Route", route.name)
                        route_doc.sf_analytics_id = route_map[route_key]
                        route_doc.save()
                        updated_routes += 1
                        print(f"Updated route: {route_key} with sf_analytics_id: {route_map[route_key]}")
                    except Exception as e:
                        print(f"Error updating route {route_key}: {str(e)}")
            
            # Commit transaction
            frappe.db.commit()
            
            # Log summary
            summary = f"""
Mapping of old entries completed:
- Total rows processed: {len(rows)}
- Cities updated: {updated_cities}
- Zones updated: {updated_zones}
- Areas updated: {updated_areas}
- Points updated: {updated_points}
- Routes updated: {updated_routes}
- Timestamp: {datetime.now()}
"""
            print(summary)
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"Mapping of old entries failed during processing: {str(e)}"
            print(error_msg)
            frappe.log_error(title="Mapping of Old Entries Failed", message=error_msg)
            raise

    except Exception as e:
        error_msg = f"Mapping of old entries failed: {str(e)}"
        print(error_msg)
        frappe.log_error(title="Mapping of Old Entries Failed", message=error_msg)
        raise

def import_routes_v2_1():
    """
    Daily cron job to import routes from analytics API with complete hierarchy.
    This function imports city, zone, area, point, and route based on the updated schema.
    Runs at the end of each day.
    """
    try:
        print(f"Starting route import v2_1 at {datetime.now()}")
        
        # Fetch data from API
        api_url = frappe.conf.get('analytics_api_url_for_routes_v2')
        api_key = frappe.conf.get('analytics_api_key_v2')
        
        if not api_url or not api_key:
            frappe.throw("Analytics API configuration missing in site config")
        
        print("Fetching data from analytics API...")
        response = requests.get(api_url, params={"api_key": api_key})
        
        if response.status_code != 200:
            frappe.throw(f"API request failed with status code: {response.status_code}")
        
        data = response.json()
        rows = data["query_result"]["data"]["rows"]
        print(f"Retrieved {len(rows)} routes from API")

        # Create maps for existing records
        city_sf_analytics_id_map = {}
        
        
        # Get existing records from Frappe
        cities = frappe.get_all("City", fields=["name", "city_name", "sf_analytics_id"], limit_page_length=None)
        for city in cities:
            if city.sf_analytics_id:
                city_sf_analytics_id_map[city.sf_analytics_id] = {
                    "name": city.name,
                    "city_name": city.city_name
                }
        
        
        print(f"Found {len(city_sf_analytics_id_map)} existing cities in system")
        
        # Process each row
        new_cities_count = 0
        
        # Start transaction
        frappe.db.begin()
        
        try:
            for row in rows:
                try:
                    # Determine state and branch based on city
                    state_name = None
                    branch = None
                    
                    if row["city"] == "BLR":
                        state_name = "Karnataka"
                        branch = "Bengaluru"
                    elif row["city"] == "HYD":
                        state_name = "Telangana"
                        branch = "Hyderabad"
                    else:
                        print(f"Unknown city code: {row['city']}, skipping row")
                        continue
                    
                    # # Get or create state
                    # state_doc = None
                    # if frappe.db.exists("State", {"state_name": state_name}):
                    #     state_doc = frappe.get_doc("State", {"state_name": state_name})
                    # else:
                    #     state_doc = frappe.get_doc({
                    #         "doctype": "State",
                    #         "state_name": state_name
                    #     })
                    #     state_doc.insert()

                    state_doc = {
                        "name": state_name,
                        "state_name": state_name
                    }
                    
                    
                    # Get or create city
                    city_doc = None
                    if row["city_id"] in city_sf_analytics_id_map:
                        # We already have the city in our map, no need to fetch it again
                        city_name = city_sf_analytics_id_map[row["city_id"]]["name"]
                    else:
                        city_doc = frappe.get_doc({
                            "doctype": "City",
                            "city_name": row["city"],
                            "state_name": state_doc["name"],
                            "sf_analytics_id": row["city_id"]
                        })
                        city_doc.insert()
                        print("\n\n")
                        print(city_doc)
                        print(city_doc.name)
                        print("\n\n")
                        # Add to map
                        city_name = city_doc.name
                        city_sf_analytics_id_map[row["city_id"]] = {
                            "name": city_name,
                            "city_name": city_doc.city_name
                        }
                        new_cities_count += 1
                    
                    
                
                except Exception as e:
                    print(f"Error processing row {row}: {str(e)}")
                    frappe.db.rollback()
                    continue
            
            # Commit transaction once at the end
            frappe.db.commit()
            
            # Log summary
            summary = f"""
Route import v2 completed:
- Total rows processed: {len(rows)}
- New cities created: {new_cities_count}
- Timestamp: {datetime.now()}
"""
            print(summary)
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"Route import v2 failed during processing: {str(e)}"
            print(error_msg)
            frappe.log_error(title="Route Import v2 Failed", message=error_msg)
            raise

    except Exception as e:
        error_msg = f"Route import v2 failed: {str(e)}"
        print(error_msg)
        frappe.log_error(title="Route Import v2 Failed", message=error_msg)
        raise 