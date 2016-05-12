# Simple Wind Vane test for SwitchDocLabs WeatherPi. Returns Analog Values and
# prints it to the screen.
# Author: Cameron Rex
# License: Public Domain

from __future__ import division
import time
import Adafruit_ADS1x15

# Note you can change the I2C address from its default (0x48), and/or the I2C
# bus by passing in these optional parameters:
adc = Adafruit_ADS1x15.ADS1015(address=0x49, busnum=3)

# Choose a gain of 1 for reading voltages from 0 to 4.09V.
# Or pick a different gain to change the range of voltages that are read:
#  - 2/3 = +/-6.144V
#  -   1 = +/-4.096V
#  -   2 = +/-2.048V
#  -   4 = +/-1.024V
#  -   8 = +/-0.512V
#  -  16 = +/-0.256V
# See table 3 in the ADS1015/ADS1115 datasheet for more info on gain.
GAIN = 2//3

# Choose a sample rate (128, 250, 490, 920, 1600, 2400, 3300)
SAMPLERATE = 250

# Set Wind Vane channel
WINDVANECH = 1


def fuzzyCompare(compareValue, value):
    """Compare used in voltageToDegrees."""
    VARYVALUE = 0.05
    if ((value > (compareValue * (1.0 - VARYVALUE))) and (value < (compareValue * (1.0 + VARYVALUE)))):
        return True
    return False


def voltageToDegrees(value, defaultWindDirection):
    """Convert voltage to degrees for wind vane."""
    # Note:  The original documentation for the wind vane says 16 positions.
    # Typically only recieve 8 positions.  And 315 degrees was wrong.
    ADJUST3OR5 = 0.66     # For 5V, use 1.0.  For 3.3V use 0.66
    if (fuzzyCompare(3.84 * ADJUST3OR5, value)):
        return 0.0
    if (fuzzyCompare(1.98 * ADJUST3OR5, value)):
        return 22.5
    if (fuzzyCompare(2.25 * ADJUST3OR5, value)):
        return 45
    if (fuzzyCompare(0.41 * ADJUST3OR5, value)):
        return 67.5
    if (fuzzyCompare(0.45 * ADJUST3OR5, value)):
        return 90.0
    if (fuzzyCompare(0.32 * ADJUST3OR5, value)):
        return 112.5
    if (fuzzyCompare(0.90 * ADJUST3OR5, value)):
        return 135.0
    if (fuzzyCompare(0.62 * ADJUST3OR5, value)):
        return 157.5
    if (fuzzyCompare(1.40 * ADJUST3OR5, value)):
        return 180
    if (fuzzyCompare(1.19 * ADJUST3OR5, value)):
        return 202.5
    if (fuzzyCompare(3.08 * ADJUST3OR5, value)):
        return 225
    if (fuzzyCompare(2.93 * ADJUST3OR5, value)):
        return 247.5
    if (fuzzyCompare(4.62 * ADJUST3OR5, value)):
        return 270.0
    if (fuzzyCompare(4.04 * ADJUST3OR5, value)):
        return 292.5
    if (fuzzyCompare(4.34 * ADJUST3OR5, value)):
        return 315.0
    if (fuzzyCompare(3.43 * ADJUST3OR5, value)):
        return 337.5
    return defaultWindDirection  # return previous value if not found

currentWindDirection = 0.0

print('Reading Wind Vane Analog Output on ADS1x15 channel 1...')
print('Reading ADS1x15 values, press Ctrl-C to quit...')
# Main loop.
while True:
    # Read the specified ADC channel using the previously set gain value.
    value = adc.read_adc(WINDVANECH, gain=GAIN, data_rate=SAMPLERATE)
    voltageValue = value / 1000 * 3
    currentWindDirection = voltageToDegrees(voltageValue, currentWindDirection)
    print("Analog: {}, Voltage: {}, Direction: {}".format(value, voltageValue, currentWindDirection))
    # Pause for half a second.
    time.sleep(0.5)
