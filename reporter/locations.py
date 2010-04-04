# This file follows pure python syntax. 
# To sun syntax check on this file `python path/to/locations.py`
# If above command does not result into traceback and returns 0, changes are good

# 3 letter codes of Hub locations.
# More at http://the-hub.pbworks.com/Hub-three-letter-codes
# Add items to the list below to support more locations
# 
LOCATION_CODES = dict (
AMS = 'Amsterdam',
ATL = 'Atlanta',
BAY = 'Bay Area',
BER = 'Berlin',
BOM = 'Bombay',
BRI = 'Bristol',
BRK = 'Berkeley',
BXL = 'Brussels',
CAI = 'Cairo',
COP = 'Copenhagen',
HFX = 'Halifax',
JHB = 'Johannesburg',
LIS = 'Islington',
LKX = 'Kings Cross',
LSB = 'Southbank',
MAD = 'Madrid',
MLN = 'Milan',
OAX = 'Oaxaca',
PTO = 'Porto',
RIG = 'Riga',
RTD = 'Rotterdam',
SFO = 'San Francisco',
SPA = 'Sao Paulo',
STH = 'Stockholm',
TLV = 'Tel Aviv',
VIE = 'Vienna',
WLD = 'Hub World'
)

LOCATION_FIELD_HELP = "Use 'Other' if you don't find your location in the list"

LOCATION_CODES2 = dict(kv[::-1] for kv in LOCATION_CODES.items())

# No edits beyond this
