WeatherPi Libraries and Example for Raspberry Pi Solar Powered Weather Station

Supports SwitchDoc Labs WeatherRack WeatherPiArduino

Version 2.0

This is a fork from the switchdoclabs/WeatherPi project

Installation:
```
sudo apt-get update
sudo apt-get install git build-essential python-dev python-pip python-smbus libi2c-dev
```
## WeatherPi:
```
cd ~
git clone https://github.com/camrex/WeatherPi.git
```
## Adafruit Python ADS1x15:
```
cd ~
git clone https://github.com/adafruit/Adafruit_Python_ADS1x15.git
cd Adafruit_Python_ADS1x15
sudo python setup.py install
```
##Adafruit Python BMP:
```
cd ~
git clone https://github.com/adafruit/Adafruit_Python_BMP.git
cd Adafruit_Python_BMP
sudo python setup.py install
```
##Adafruit Python GPIO Library:
```
cd ~
git clone https://github.com/adafruit/Adafruit_Python_GPIO.git
cd Adafruit_Python_GPIO
sudo python setup.py install
```
##AS3935:
```
cd ~
git clone https://github.com/pcfens/RaspberryPi-AS3935```
cd RaspberryPi-AS3935
sudo python setup.py install
```
##AM2315:
```
sudo pip install tentacle_pi
```

SwitchDocLabs Documentation for WeatherRack/WeatherPiArduino under products on:

http://www.switchdoc.com/
```
April 25, 2016 - Forked from switchdoclabs/WeatherPi, Reworked Adafruit library imports, AS3935 import, reworked conf
March 28, 2015 - added subdirectories
May 9, 2015 - Updated software for WatchDog Timer and Email
May 10, 2015 - Added mysql table SQL files for database building 
```
