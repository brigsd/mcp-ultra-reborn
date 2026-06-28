MM_PER_M = 1000.0


def mm_to_m(value):
    return float(value) / MM_PER_M


def m_to_mm(value):
    return float(value) * MM_PER_M


def dimensions_mm_to_m(dimensions):
    return {key: mm_to_m(value) for key, value in dimensions.items()}

