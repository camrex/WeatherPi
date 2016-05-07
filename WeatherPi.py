#!/usr/bin/env python
"""Main WeatherPi program."""
#
# Weather Pi Solar Powered Weather Station
# Version 2.0 April 25, 2016
# Modified by Cameron Rex (camrex)
#
# Original Project:
# WeatherPi Solar Powered Weather Station
# Version 1.4 April 11, 2015
# SwitchDoc Labs
# www.switchdoc.com
#
#

import sys

sys.path.append('./RTC_SDL_DS3231')
sys.path.append('./SDL_Pi_Weather_80422')
sys.path.append('./SDL_Pi_FRAM')
sys.path.append('./SDL_Pi_INA3221')
sys.path.append('./UnitConv')

# Imports
import time
from datetime import datetime
import os
import sendemail
import pclogging
import MySQLdb as mdb
from tentacle_pi.AM2315 import AM2315
import subprocess
import RPi.GPIO as GPIO
import SDL_Pi_INA3221
import SDL_DS3231
import Adafruit_BMP.BMP085 as BMP180
import SDL_Pi_Weather_80422 as SDL_Pi_Weather_80422
from RPi_AS3935 import RPi_AS3935
import conv_temp
import conv_pressure
# import random
# import re
# import math
# import doAllGraphs
# import urllib2
# import SDL_Pi_FRAM

# Check for user imports
try:
    import conflocal as conf
except ImportError:
    import conf

################
# GPIO Setup
################
GPIO.setmode(GPIO.BCM)
WATCHDOGTRIGGER = 17
LIGHTNINGPIN = 22
ANENOMETERPIN = 23
RAINPIN = 24
# SUNAIRLEDPIN = 25

################
# SunAirPlus Sensors
ina3221 = SDL_Pi_INA3221.SDL_Pi_INA3221(twi=4, addr=0x40)
LIPO_BATTERY_CHANNEL = 1
SOLAR_CELL_CHANNEL = 2
OUTPUT_CHANNEL = 3
################

# WeatherRack Weather Sensors
# constants
SDL_MODE_INTERNAL_AD = 0
SDL_MODE_I2C_ADS1015 = 1
SDL_MODE_SAMPLE = 0  # sample mode means return immediately.  THe wind speed is averaged at sampleTime or when you ask, whichever is longer
SDL_MODE_DELAY = 1  # Delay mode means to wait for sampleTime and the average after that time.

weatherStation = SDL_Pi_Weather_80422.SDL_Pi_Weather_80422(ANENOMETERPIN, RAINPIN, 0, 0, SDL_MODE_I2C_ADS1015)
weatherStation.setWindMode(SDL_MODE_SAMPLE, 5.0)
# weatherStation.setWindMode(SDL_MODE_DELAY, 5.0)
################

# DS3231/AT24C32 Setup
starttime = datetime.utcnow()
ds3231 = SDL_DS3231.SDL_DS3231(3, 0x68, 0x57)
ds3231.write_now()     # comment out line after the clock has been initialized
################

# BMP180 Setup (compatible with BMP085)
bmp180 = BMP180.BMP085()

################
# ad3935 Set up Lightning Detector
as3935 = RPi_AS3935(address=0x03, bus=5)
as3935.set_indoors(True)
as3935.set_noise_floor(0)
as3935.calibrate(tun_cap=0x0F)
as3935LastInterrupt = 0
as3935LightningCount = 0
as3935LastDistance = 0
as3935LastStatus = ""
as3935Interrupt = False


def process_as3935_interrupt():
    """Process the AS3935 Interrupt to determine type."""
    global as3935Interrupt
    global as3935, as3935LastInterrupt, as3935LastDistance, as3935LastStatus
    as3935Interrupt = False
    print "processing Interrupt from as3935"
    reason = as3935.get_interrupt()
    as3935LastInterrupt = reason
    if reason == 0x00:
        as3935LastStatus = "Spurious Interrupt"
    if reason == 0x01:
        as3935LastStatus = "Noise Floor too low. Adjusting"
        as3935.raise_noise_floor()
    if reason == 0x04:
        as3935LastStatus = "Disturber detected - masking"
        as3935.set_mask_disturber(True)
    if reason == 0x08:
        now = datetime.now().strftime('%H:%M:%S - %Y/%m/%d')
        distance = as3935.get_distance()
        as3935LastDistance = distance
        as3935LastStatus = "Lightning Detected " + str(distance) + "km away. (%s)" % now
        pclogging.log(pclogging.INFO, __name__, "Lightning Detected " + str(distance) + "km away. (%s)" % now)
        sendemail.sendEmail("test", "WeatherPi Lightning Detected\n", as3935LastStatus, conf.textnotifyAddress,  conf.textfromAddress, "")
    print "Last Interrupt = 0x%x:  %s" % (as3935LastInterrupt, as3935LastStatus)


def handle_as3935_interrupt(channel):
    """Receive Interupt, log and flag."""
    global as3935Interrupt
    print "as3935 Interrupt"
    as3935Interrupt = True

GPIO.setup(LIGHTNINGPIN, GPIO.IN)
GPIO.add_event_detect(LIGHTNINGPIN, GPIO.RISING, callback=handle_as3935_interrupt)

# Setup AM2315
am2315 = AM2315(0x5c, "/dev/i2c-4")


# Set up FRAM
# fram = SDL_Pi_FRAM.SDL_Pi_FRAM(addr=0x50, twi=3)


# Main Program Loop - sleeps 10 seconds
def returnPercentLeftInBattery(currentVoltage, maxVolt):
    """Determine percent battery remaining."""
    scaledVolts = currentVoltage / maxVolt
    if (scaledVolts > 1.0):
        scaledVolts = 1.0
    elif (scaledVolts > .9686):
        returnPercent = 10*(1-(1.0-scaledVolts)/(1.0-.9686))+90
        return returnPercent
    elif (scaledVolts > 0.9374):
        returnPercent = 10*(1-(0.9686-scaledVolts)/(0.9686-0.9374))+80
        return returnPercent
    elif (scaledVolts > 0.9063):
        returnPercent = 30*(1-(0.9374-scaledVolts)/(0.9374-0.9063))+50
        return returnPercent
    elif (scaledVolts > 0.8749):
        returnPercent = 30*(1-(0.8749-scaledVolts)/(0.9063-0.8749))+20
        return returnPercent
    elif (scaledVolts > 0.8437):
        returnPercent = 17*(1-(0.8437-scaledVolts)/(0.8749-0.8437))+3
        return returnPercent
    elif (scaledVolts > 0.8126):
        returnPercent = 1*(1-(0.8126-scaledVolts)/(0.8437-0.8126))+2
        return returnPercent
    elif (scaledVolts > 0.7812):
        returnPercent = 1*(1-(0.7812-scaledVolts)/(0.7812-0.8126))+1
        return returnPercent
    return 0


def sampleWeather():
    """Sample weather sensors."""
    global as3935LightningCount
    global as3935, as3935LastInterrupt, as3935LastDistance, as3935LastStatus
    global currentWindSpeed, currentWindGust, totalRain
    global bmp180Temperature, bmp180Pressure, bmp180Altitude, bmp180SeaLevel
    global outsideTemperature, outsideHumidity, crc_check
    global currentWindDirection, currentWindDirectionVoltage
    global HTUtemperature, HTUhumidity
    global dstemp

    print "----------------- "
    print " Weather Sampling"
    print "----------------- "

    currentWindSpeed = weatherStation.current_wind_speed() / 1.6
    currentWindGust = weatherStation.get_wind_gust() / 1.6
    totalRain = 0
    totalRain = weatherStation.get_current_rain_total() / 25.4
    currentWindDirection = weatherStation.current_wind_direction()
    currentWindDirectionVoltage = weatherStation.current_wind_direction_voltage()

    bmp180Temperature = bmp180.read_temperature()
    bmp180Temperature = conv_temp.celsius_to_fahrenheit(bmp180.read_temperature())
    bmp180Pressure = conv_pressure.hpa_to_inches(bmp180.read_pressure() / 100)
    bmp180Altitude = bmp180.read_altitude() * 3.280839895
    bmp180SeaLevel = conv_pressure.hpa_to_inches(bmp180.read_sealevel_pressure() / 100)

    # We use a C library for this device as it just doesn't play well with Python and smbus/I2C libraries
    HTU21DFOut = subprocess.check_output(["htu21dflib/htu21dflib", "-l"])
    splitstring = HTU21DFOut.split()
    HTUtemperature = conv_temp.celsius_to_fahrenheit(float(splitstring[0]))
    HTUhumidity = float(splitstring[1])

    if (as3935LastInterrupt == 0x00):
        as3935InterruptStatus = "----No Lightning detected---"
    if (as3935LastInterrupt == 0x01):
        as3935InterruptStatus = "Noise Floor: %s" % as3935LastStatus
        as3935LastInterrupt = 0x00
    if (as3935LastInterrupt == 0x04):
        as3935InterruptStatus = "Disturber: %s" % as3935LastStatus
        as3935LastInterrupt = 0x00
    if (as3935LastInterrupt == 0x08):
        as3935InterruptStatus = "Lightning: %s" % as3935LastStatus
        as3935LightningCount += 1
        as3935LastInterrupt = 0x00

    # get AM2315 Outside Humidity and Outside Temperature
    outsideTemperature, outsideHumidity, crc_check = am2315.sense()
    outsideTemperature = conv_temp.celsius_to_fahrenheit(outsideTemperature)

    # get DS3231 temperature
    dstemp = conv_temp.celsius_to_fahrenheit(ds3231.getTemp())

def sampleSunAirPlus():
    """Sample SunAirPlus."""
    global batteryVoltage, batteryCurrent, solarVoltage, solarCurrent, loadVoltage, loadCurrent
    global batteryPower, solarPower, loadPower, batteryCharge

    print "----------------- "
    print " SunAirPlus Sampling"
    print "----------------- "
    busvoltage1 = ina3221.getBusVoltage_V(LIPO_BATTERY_CHANNEL)
    shuntvoltage1 = ina3221.getShuntVoltage_mV(LIPO_BATTERY_CHANNEL)
    # - means the battery is charging, + that it is discharging
    batteryCurrent = ina3221.getCurrent_mA(LIPO_BATTERY_CHANNEL)
    batteryVoltage = busvoltage1 + (shuntvoltage1 / 1000)
    batteryPower = batteryVoltage * (batteryCurrent / 1000)
    busvoltage2 = ina3221.getBusVoltage_V(SOLAR_CELL_CHANNEL)
    shuntvoltage2 = ina3221.getShuntVoltage_mV(SOLAR_CELL_CHANNEL)
    solarCurrent = -ina3221.getCurrent_mA(SOLAR_CELL_CHANNEL)
    solarVoltage = busvoltage2 + (shuntvoltage2 / 1000)
    solarPower = solarVoltage * (solarCurrent / 1000)
    busvoltage3 = ina3221.getBusVoltage_V(OUTPUT_CHANNEL)
    shuntvoltage3 = ina3221.getShuntVoltage_mV(OUTPUT_CHANNEL)
    loadCurrent = ina3221.getCurrent_mA(OUTPUT_CHANNEL)
    loadVoltage = busvoltage3 + (shuntvoltage3 / 1000)
    loadPower = loadVoltage * (loadCurrent / 1000)
    batteryCharge = returnPercentLeftInBattery(batteryVoltage, 4.19)


def display():
    """Display values."""
    print "----------------- "
    print " WeatherRack Weather Sensors Sampling"
    print "----------------- "
    print "Rain Total=\t%0.2f in" % (totalRain)
    print "Wind Speed=\t%0.2f MPH" % (currentWindSpeed)
    print "MPH wind_gust=\t%0.2f MPH" % (currentWindGust)
    print "Wind Direction=\t\t\t %0.2f Degrees" % (currentWindDirection)
    print "Wind Direction Voltage=\t\t %0.3f V" % (currentWindDirectionVoltage)
    print

    print "----------------- "
    print " DS3231 Real Time Clock"
    print "----------------- "
    print "Raspberry Pi=\t" + time.strftime("%Y-%m-%d %H:%M:%S")
    print "DS3231=\t\t%s" % ds3231.read_datetime()
    print "DS3231 Temperature= \t%0.2f F" % ds3231.getTemp() * 1.8 + 32
    print

    print "----------------- "
    print " BMP180 Barometer/Temp/Altitude"
    print "----------------- "
    print "Temperature = \t{0:0.2f} F" % (bmp180Temperature)
    print "Pressure = \t{0:0.2f} inHg" % (bmp180Pressure)
    print "Altitude = \t{0:0.2f} ft" % (bmp180Altitude)
    print "Sealevel Pressure = \t{0:0.2f} inHg" % (bmp180SeaLevel)
    print

    print "----------------- "
    print " HTU21DF Humidity and Temperature"
    print "----------------- "
    print "Temperature = \t%0.2f F" % (HTUtemperature)
    print "Humidity = \t%0.2f %%" % (HTUhumidity)
    print

    print "----------------- "
    print " AS3853 Lightning Detector "
    print "----------------- "
    print "Last result from AS3953:"
    if (as3935LastInterrupt == 0x00):
        print "----No Lightning detected---"
    if (as3935LastInterrupt == 0x01):
        print "Noise Floor: %s" % as3935LastStatus
        as3935LastInterrupt = 0x00
    if (as3935LastInterrupt == 0x04):
        print "Disturber: %s" % as3935LastStatus
        as3935LastInterrupt = 0x00
    if (as3935LastInterrupt == 0x08):
        print "Lightning: %s" % as3935LastStatus
        as3935LightningCount += 1
        as3935LastInterrupt = 0x00
    print "Lightning Count = ", as3935LightningCount
    print

    print "----------------- "
    print "AM2315 "
    print "----------------- "
    print "outsideTemperature: %0.1f F" % outsideTemperature
    print "outsideHumidity: %0.1f %%" % outsideHumidity
    print "crc: %s" % crc_check
    print

    print "----------------- "
    print "SunAirPlus Currents / Voltage "
    print "----------------- "
    print "LIPO_Battery Bus Voltage: %3.2f V " % busvoltage1
    print "LIPO_Battery Shunt Voltage: %3.2f mV " % shuntvoltage1
    print "LIPO_Battery Load Voltage:  %3.2f V" % loadvoltage1
    print "LIPO_Battery Current 1:  %3.2f mA" % current_mA1
    print "Battery Power 1:  %3.2f W" % batteryPower
    print
    print "Solar Cell Bus Voltage 2:  %3.2f V " % busvoltage2
    print "Solar Cell Shunt Voltage 2: %3.2f mV " % shuntvoltage2
    print "Solar Cell Load Voltage 2:  %3.2f V" % loadvoltage2
    print "Solar Cell Current 2:  %3.2f mA" % current_mA2
    print "Solar Cell Power 2:  %3.2f W" % solarPower
    print
    print "Output Bus Voltage 3:  %3.2f V " % busvoltage3
    print "Output Shunt Voltage 3: %3.2f mV " % shuntvoltage3
    print "Output Load Voltage 3:  %3.2f V" % loadvoltage3
    print "Output Current 3:  %3.2f mA" % current_mA3
    print "Output Power 3:  %3.2f W" % loadPower
    print
    print "------------------------------"


def writeWeatherRecord():
    """Write weather sensor data to database."""
    con = None
    cur = None
    try:
        print("Connecting to Database")
        con = mdb.connect(conf.DATABASEHOST, conf.DATABASEUSER, conf.DATABASEPASSWORD, conf.DATABASENAME)
        cur = con.cursor()
        print "------Writing Weather Data------"
        query = 'INSERT INTO WeatherData(TimeStamp,as3935LightningCount, as3935LastInterrupt, as3935LastDistance, as3935LastStatus, currentWindSpeed, currentWindGust, totalRain,  bmp180Temperature, bmp180Pressure, bmp180Altitude,  bmp180SeaLevel,  outsideTemperature, outsideHumidity, currentWindDirection, currentWindDirectionVoltage, insideTemperature, insideHumidity) VALUES(UTC_TIMESTAMP(), %.3f, %.3f, %.3f, "%s", %.3f, %.3f, %.3f, %i, %.3f, %.3f, %.3f, %.3f, %.3f, %.3f, %.3f, %.3f, %.3f)' % (as3935LightningCount, as3935LastInterrupt, as3935LastDistance, as3935LastStatus, currentWindSpeed, currentWindGust, totalRain,  bmp180Temperature, bmp180Pressure, bmp180Altitude,  bmp180SeaLevel,  outsideTemperature, outsideHumidity, currentWindDirection, currentWindDirectionVoltage, HTUtemperature, HTUhumidity)
        print("query=%s" % query)
        cur.execute(query)
        con.commit()
    except mdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        if con is not None:
            con.rollback()
    finally:
        if cur is not None:
            cur.close()
        if con is not None:
            con.close()
        del cur
        del con


def writePowerRecord():
    """Write power data to database."""
    con = None
    cur = None
    try:
        print("Connecting to Database")
        con = mdb.connect(conf.DATABASEHOST, conf.DATABASEUSER, conf.DATABASEPASSWORD, conf.DATABASENAME)
        cur = con.cursor()
        print "------Writing Power Data------"
        query = 'INSERT INTO PowerSystem(TimeStamp, batteryVoltage, batteryCurrent, solarVoltage, solarCurrent, loadVoltage, loadCurrent, batteryPower, solarPower, loadPower, batteryCharge) VALUES (UTC_TIMESTAMP (), %.3f, %.3f, %.3f, %.3f, %.3f, %.3f, %.3f, %.3f, %.3f, %.3f)' % (batteryVoltage, batteryCurrent, solarVoltage, solarCurrent, loadVoltage, loadCurrent, batteryPower, solarPower, loadPower, batteryCharge)
        print("query=%s" % query)
        cur.execute(query)
        con.commit()
    except mdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        if con is not None:
            con.rollback()
    finally:
        if cur is not None:
            cur.close()
        if con is not None:    
            con.close()
        del cur
        del con


def writeWeewxInputFile():
    """Write weewx input file."""
    f = open("/home/pi/WeatherPi/output/wxdata", "w")
    # f.write("barometer = \t{0:0.2f} \n" % (bmp180Pressure))
    f.write("pressure = %0.2f \n" % (bmp180Pressure))
    f.write("altimeter = %0.2f \n" % (bmp180Altitude))
    f.write("inTemp = %0.2f \n" % (bmp180Temperature))
    f.write("outTemp = %0.2f \n" % (outsideTemperature))
    f.write("inHumidity = %0.2f \n" % (HTUhumidity))
    f.write("outHumidity = %0.1f \n" % outsideHumidity)
    f.write("windSpeed = %0.2f \n" % (currentWindSpeed))
    f.write("windDir = %0.2f \n" % (currentWindDirection))
    f.write("windGust = %0.2f \n" % (currentWindGust))
    # f.write("windGustDir = ")
    # f.write("rainRate = ")
    f.write("rain = %0.2f \n" % (totalRain))
    # f.write("dewpoint = ")
    # f.write("windchill = ")
    # f.write("headindex = ")
    # f.write("ET = ")
    # f.write("radiation = ")
    # f.write("UV = ")
    f.write("extraTemp1 = %0.2f \n" % (HTUtemperature))
    f.write("extraTemp2 = %0.2f \n" % (dstemp))
    # f.write("extraTemp3 = ")
    # f.write("soilTemp1 = ")
    # f.write("soilTemp2 = ")
    # f.write("soilTemp3 = ")
    # f.write("soilTemp4 = ")
    # f.write("leafTemp1 = ")
    # f.write("leafTemp2 = ")
    # f.write("extraHumid1 = ")
    # f.write("extraHumid2 = ")
    # f.write("soilMoist1 = ")
    # f.write("soilMoist2 = ")
    # f.write("soilMoist3 = ")
    # f.write("soilMoist4 = ")
    # f.write("leafWet1 = ")
    # f.write("leafWet2 = ")
    # f.write("rxCheckPercent = ")
    # f.write("txBatteryStatus = ")
    # f.write("consBatteryVoltage = ")
    # f.write("hail = ")
    # f.write("hailRate = ")
    # f.write("heatingTemp = ")
    # f.write("heatingVoltage = ")
    # f.write("supplyVoltage = ")
    # f.write("referenceVoltage = ")
    # f.write("windBatteryStatus = ")
    # f.write("rainBatteryStatus = ")
    # f.write("outTempBatteryStatus = ")
    # f.write("inTempBatteryStatus = ")
    f.close()


def patTheDog():
    """Pat the dog."""
    print "------Patting The Dog------- "
    GPIO.setup(WATCHDOGTRIGGER, GPIO.OUT)
    GPIO.output(WATCHDOGTRIGGER, False)
    time.sleep(0.2)
    GPIO.output(WATCHDOGTRIGGER, True)
    GPIO.setup(WATCHDOGTRIGGER, GPIO.IN)


def shutdownPi(why):
    """Shutdown Pi."""
    pclogging.log(pclogging.INFO, __name__, "Pi Shutting Down: %s" % why)
    sendemail.sendEmail("test", "WeatherPi Shutting down:" + why, "The WeatherPi Raspberry Pi shutting down.", conf.notifyAddress,  conf.fromAddress, "")
    sys.stdout.flush()
    time.sleep(10.0)
    os.system("sudo shutdown -h now")


def rebootPi(why):
    """Reboot Pi."""
    pclogging.log(pclogging.INFO, __name__, "Pi Rebooting: %s" % why)
    os.system("sudo shutdown -r now")


WLAN_check_flg = 0


def WLAN_check():
    """Check to see if WLAN is still up by pinging router."""
    global WLAN_check_flg
    ping_ret = subprocess.call(['ping -c 2 -w 1 -q 192.168.1.1 |grep "1 received" > /dev/null 2> /dev/null'], shell=True)
    if ping_ret:
        # we lost the WLAN connection.
        # did we try a recovery already?
        if (WLAN_check_flg > 2):
            # we have a serious problem and need to reboot the Pi to recover the WLAN connection
            print "logger WLAN Down, Pi is forcing a reboot"
            pclogging.log(pclogging.ERROR, __name__, "WLAN Down, Pi is forcing a reboot")
            WLAN_check_flg = 0
            rebootPi("WLAN Down")
        elif (WLAN_check_flg == 1):
            # try to recover the connection by resetting the LAN
            print "WLAN Down, Pi is trying resetting WLAN connection"
            pclogging.log(pclogging.WARNING, __name__, "WLAN Down, Pi is resetting WLAN connection")
            WLAN_check_flg = WLAN_check_flg + 1  # try to recover
            subprocess.call(['sudo /sbin/ifdown wlan0 && sleep 10 && sudo /sbin/ifup --force wlan0'], shell=True)
        else:
            WLAN_check_flg = 0
            print "WLAN is OK"

print ""
print "WeatherPi Solar Powered Weather Station Version 2.0"
print "Updated by Cameron Rex (camrex) - Original code by SwitchDoc Labs"
print ""
print "Program Started at:" + time.strftime("%Y-%m-%d %H:%M:%S")
print ""

pclogging.log(pclogging.INFO, __name__, "WeatherPi Startup Version 2.0")
sendemail.sendEmail("test", "WeatherPi Startup \n", "The WeatherPi Raspberry Pi has rebooted.", conf.notifyAddress,  conf.fromAddress, "")

secondCount = 1
while True:
    # process Interrupts from Lightning
    if (as3935Interrupt is True):
        try:
            process_as3935_interrupt()
        except:
            print "exception - as3935 I2C did not work"

    # print every 10 seconds
    if ((secondCount % 10) == 0):
        sampleWeather()
        sampleSunAirPlus()
        writeWeatherRecord()
        writePowerRecord()
        writeWeewxInputFile()
        # display()
        patTheDog()      # reset the WatchDog Timer

    # every 5 minutes (300 seconds), push data to mysql and check for shutdown
    if ((secondCount % (5 * 60)) == 0):
        if (batteryVoltage < 3.5):
            print "--->>>>Time to Shutdown<<<<---"
            shutdownPi("low voltage shutdown")

    # every 30 (1800 seconds) minutes, check wifi connections
    if ((secondCount % (30*60)) == 0):
        WLAN_check()

    # every 48 hours, reboot
    if ((secondCount % (60*60*48)) == 0):
        rebootPi("48 hour reboot")

    secondCount = secondCount + 1

    # reset secondCount to prevent overflow forever
    if (secondCount == 1000001):
        secondCount = 1

    time.sleep(1.0)
