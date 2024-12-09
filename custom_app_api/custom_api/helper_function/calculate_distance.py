from math import sin, cos, sqrt, atan2, radians

def calculate_total_distance(coordinates):
    """
    Calculate the total distance covered by an array of coordinates using the Haversine formula.
    
    Args:
        coordinates (list): A list of [latitude, longitude] pairs.

    Returns:
        float: The total distance in kilometers.
    """
    # Approximate radius of earth in km
    R = 6373.0

    total_distance = 0.0

    for i in range(len(coordinates) - 1):
        # Get the latitude and longitude of the current and next points
        lat1, lon1 = radians(coordinates[i][0]), radians(coordinates[i][1])
        lat2, lon2 = radians(coordinates[i + 1][0]), radians(coordinates[i + 1][1])

        # Compute the differences in latitude and longitude
        dlon = lon2 - lon1
        dlat = lat2 - lat1

        # Haversine formula
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        # Distance between the two points
        distance = R * c
        total_distance += distance

    return total_distance

# Array of coordinates
coordinates = [
    [17.4097146, 78.4207672], [17.4097139, 78.4207661], [17.4096921, 78.4204013],
    [17.4097387, 78.4204186], [17.4097278, 78.420414], [17.4087164, 78.4193608],
    [17.4091418, 78.418738], [17.4111981, 78.4174884], [17.4118324, 78.4161638],
    [17.411961, 78.4137828], [17.4124338, 78.4121375], [17.4133419, 78.4116704],
    [17.4145473, 78.4117425], [17.4159193, 78.4113788], [17.4163351, 78.4105468],
    [17.4156663, 78.4100797], [17.4174255, 78.4109844], [17.419261, 78.4122962],
    [17.420721, 78.4114246], [17.421854, 78.4109443], [17.4239498, 78.4105],
    [17.4255944, 78.4083834], [17.4273585, 78.4060595], [17.4288543, 78.4043466],
    [17.4302156, 78.4029541], [17.4319902, 78.4001826], [17.4332531, 78.3982951],
    [17.4347715, 78.3959793], [17.436238, 78.395048], [17.4371354, 78.3930001],
    [17.4382384, 78.3921385], [17.4374217, 78.390424], [17.4370547, 78.3887623],
    [17.433615, 78.3880944], [17.4318356, 78.3884087], [17.4341376, 78.3881918]
]

# Calculate and print the total distance
total_distance = calculate_total_distance(coordinates)
print("Total Distance:", total_distance, "km")
