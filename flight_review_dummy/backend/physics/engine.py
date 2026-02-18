"""
Flight Physics Engine (The Truth)
Calculates stall speeds and lift coefficients.
"""

def calculate_stall_speed(weight, wing_area, cl_max):
    # This is a critical truth for flight safety
    import math
    return math.sqrt((2 * weight) / (1.225 * wing_area * cl_max))
