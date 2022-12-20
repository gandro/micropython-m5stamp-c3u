# Copyright (c) 2022 Sebastian Wicki
# SPDX-License-Identifier: MIT

import json
import machine
import neopixel
import network
import sys
import time
import uasyncio

import bh1750fvi
import qmp6988
import sgp30
import sht30

from homeassist import HomeAssistant, Sensor


async def main():
    ha = HomeAssistant(cfg["ha_host"], cfg["ha_port"], cfg["ha_ssl"], cfg["ha_token"])

    light_sensor = Sensor("light", "lx", "illuminance", "Ambient Light")
    temp_sensor = Sensor("temp", "°C", "temperature", "Temperature")
    humidity_sensor = Sensor("humidity", "%", "humidity", "Humidity")
    eco2_sensor = Sensor("eco2", "ppm", "carbon_dioxide", "CO₂")
    tvoc_sensor = Sensor(
        "tvoc", "ppb", "volatile_organic_compounds", "Total VOC")
    temp_alt_sensor = Sensor("temp_alt", "°C", "temperature", "Temperature")
    pressure_sensor = Sensor("pressure", "Pa", "pressure", "Pressure")

    dlx = bh1750fvi.BH1750FVI(i2c)
    rht = sht30.SHT30(i2c)
    voc = sgp30.SGP30(i2c)
    prt = qmp6988.QMP6988(i2c)

    await voc.start()


    while True:
        loop_start = time.ticks_ms()

        light = dlx.measure()
        temp, humidity = rht.measure()

        voc.set_absolute_humidity(sgp30.absolute_humidity(temp, humidity))
        eco2, tvoc = voc.measure()
        temp_alt, pressure = prt.measure()

        await ha.submit(light_sensor, light)

        await ha.submit(temp_sensor, temp)
        await ha.submit(humidity_sensor, humidity)

        await ha.submit(eco2_sensor, eco2)
        await ha.submit(tvoc_sensor, tvoc)

        await ha.submit(temp_alt_sensor, temp_alt)
        await ha.submit(pressure_sensor, pressure)

        loop_end = time.ticks_ms()
        await uasyncio.sleep_ms(30_000 - time.ticks_diff(loop_end, loop_start))

def i2c_ready():
    devices = i2c.scan()
    ready = bh1750fvi.I2C_DEFAULT_ADDR in devices
    ready &= sht30.I2C_DEFAULT_ADDR in devices
    ready &= sgp30.I2C_DEFAULT_ADDR in devices
    ready &= qmp6988.I2C_DEFAULT_ADDR in devices
    return ready

LED_STAGE_1 = (0, 0, 1)
LED_STAGE_2 = (0, 1, 1)
LED_STAGE_3 = (1, 1, 1)
LED_BUSY = (1, 0, 1)
LED_ERROR = (1, 0, 0)
LED_OFF = (0, 0, 0)

def led_status(c):
    led.fill(c)
    led.write()

async def watchdog_feed():
    while True:
        await uasyncio.sleep(1)
        wdt.feed()

async def liveness_check():
    while True:
        if not button.value():
            led_status(LED_BUSY)
        else:
            led_status(LED_OFF)
        await uasyncio.sleep_ms(250)

def error_handler(_, context):
    led_status(LED_ERROR)
    if "message" in context:
        print(context["message"])
    if "future" in context:
        print("future:", context["future"], "coro=", context["future"].coro)
    if "exception" in context:
        sys.print_exception(context["exception"])
    print("Resetting in 10 seconds...")
    time.sleep(10)
    machine.reset()

# Escape hatch before we set up the Watchdog
button = machine.Pin(9, machine.Pin.IN, machine.Pin.PULL_UP)
if not button.value():
    print("Entering safe mode...")
    sys.exit()

# Setting up Watchdog. This requires boot-up to complete in 15 seconds
wdt = machine.WDT(timeout=15_000)
led = neopixel.NeoPixel(machine.Pin(2, machine.Pin.OUT), 1)

led_status(LED_STAGE_1)
print("Loading configuration...")
with open("config.json") as f:
    cfg = json.load(f)

led_status(LED_STAGE_2)
print("Connecting to network...")
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(cfg["wifi_ssid"], cfg["wifi_key"])

led_status(LED_STAGE_3)
print("Waiting for devices to become ready...")
i2c = machine.SoftI2C(sda=machine.Pin(1), scl=machine.Pin(0), freq=400000)
while not (i2c_ready() and wifi.isconnected()):
    time.sleep_ms(100)

led_status(LED_OFF)
print("Starting main event loop...")
loop = uasyncio.new_event_loop()
loop.set_exception_handler(error_handler)
loop.create_task(watchdog_feed())
loop.create_task(liveness_check())
loop.run_until_complete(main())