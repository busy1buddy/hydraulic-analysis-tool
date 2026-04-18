"""
Australian Pipeline Asset Cost Database (WSAA-aligned)
====================================================
Contains typical unit rates for pipe supply, trenching, and installation
in AUD/m, categorized by diameter and material.
"""

# Typical Pipe Supply Rates (AUD/m) - PE100 PN16 (SDR 11)
PIPE_SUPPLY_RATES = {
    63: 8.50,
    90: 16.20,
    110: 24.50,
    160: 52.00,
    200: 82.00,
    250: 125.00,
    315: 198.00,
    355: 252.00,
    400: 320.00,
    450: 410.00,
    500: 505.00,
    630: 802.00,
}

# Typical Installation Rates (AUD/m) - Includes Trenching, Bedding, Backfill
# Based on depth ~1.0m, standard soil (non-rock)
PIPE_INSTALL_RATES = {
    63: 65.00,
    90: 85.00,
    110: 110.00,
    160: 155.00,
    200: 195.00,
    250: 250.00,
    315: 320.00,
    355: 380.00,
    400: 450.00,
    450: 520.00,
    500: 610.00,
    630: 880.00,
}

# Maintenance OPEX Rates (AUD/km/year)
MAINTENANCE_RATES = {
    'PVC': 850.0,
    'PE': 750.0,
    'DI': 1200.0,
    'CI': 2500.0,
    'Steel': 1800.0,
    'Concrete': 1500.0,
}

def get_total_unit_rate(dn_mm, sdr=11, soil_factor=1.0):
    """
    Get estimated total installed cost per metre.
    """
    supply = PIPE_SUPPLY_RATES.get(dn_mm, dn_mm * 1.0) # Fallback
    install = PIPE_INSTALL_RATES.get(dn_mm, dn_mm * 1.5) # Fallback
    
    return (supply + install * soil_factor)
