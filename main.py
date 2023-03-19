# Copyright (c) 2023 Sebastian Wicki
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
import scd40
import sht30

from homeassist import HomeAssistant, Sensor


async def main():
    ha = HomeAssistant(cfg["ha_host"], cfg["ha_port"],
                       cfg["ha_ssl"], cfg["ha_token"])

    dlx = bh1750fvi.BH1750FVI(i2c)
    light_bh1750fvi_sensor = Sensor(
        "light_bh1750fvi", "lx", "illuminance", "Ambient Light")

    rht = sht30.SHT30(i2c)
    temp_sht30_sensor = Sensor(
        "temp_sht30", "°C", "temperature", "Temperature")
    humidity_sht30_sensor = Sensor(
        "humidity_sht30", "%", "humidity", "Humidity")

    scd = scd40.SCD40(i2c)
    co2_scd40_sensor = Sensor("co2_scd40", "ppm", "carbon_dioxide", "CO₂")
    temp_scd40_sensor = Sensor(
        "temp_scd40", "°C", "temperature", "Temperature")
    humidity_scd40_sensor = Sensor(
        "humidity_scd40", "%", "humidity", "Humidity")

    prt = qmp6988.QMP6988(i2c)
    temp_qmp6988_sensor = Sensor(
        "temp_qmp6988", "°C", "temperature", "Temperature")
    pressure_qmp6988_sensor = Sensor(
        "pressure_qmp6988", "Pa", "pressure", "Pressure")

    await scd.start()

    led.color(LED_OFF)
    print("Starting main event loop...")

    while True:
        loop_start = time.ticks_ms()

        light_bh1750fvi = dlx.measure()
        temp_sht30, humidity_sht30 = rht.measure()
        temp_qmp6988, pressure_qmp6988 = prt.measure()
        scd.set_ambient_pressure(pressure_qmp6988)
        co2_scd40, temp_scd40, humidity_scd40 = scd.measure()

        await ha.submit(light_bh1750fvi_sensor, light_bh1750fvi)

        await ha.submit(temp_sht30_sensor, temp_sht30)
        await ha.submit(humidity_sht30_sensor, humidity_sht30)

        await ha.submit(temp_qmp6988_sensor, temp_qmp6988)
        await ha.submit(pressure_qmp6988_sensor, pressure_qmp6988)

        await ha.submit(co2_scd40_sensor, co2_scd40)
        await ha.submit(temp_scd40_sensor, temp_scd40)
        await ha.submit(humidity_scd40_sensor, humidity_scd40)

        loop_end = time.ticks_ms()
        await uasyncio.sleep_ms(30_000 - time.ticks_diff(loop_end, loop_start))


async def watchdog_feed():
    while True:
        await uasyncio.sleep(1)
        wdt.feed()


async def liveness_check():
    last_color = None
    while True:
        if not button.value():
            if last_color is None:
                last_color = led.color()
            led.color(LED_LIVENESS)
        else:
            led.color(last_color)
            last_color = None
        await uasyncio.sleep_ms(100)


def error_handler(_, context):
    led.color(LED_ERROR)
    if "message" in context:
        print(context["message"])
    if "future" in context:
        print("future:", context["future"], "coro=", context["future"].coro)
    if "exception" in context:
        sys.print_exception(context["exception"])
    print("Resetting in 10 seconds...")
    time.sleep(10)
    machine.reset()


LED_CONFIG = (0, 0, 10)
LED_NETWORK = (10, 10, 1)
LED_DEVICES = (0, 10, 1)
LED_LIVENESS = (10, 10, 10)

LED_ERROR = (10, 0, 0)
LED_OFF = (0, 0, 0)


class LED:
    def __init__(self, pin):
        self.led = neopixel.NeoPixel(pin, 1)

    def color(self, c=None):
        if c is None:
            return self.led[0]
        self.led[0] = c
        self.led.write()


def i2c_ready():
    devices = i2c.scan()
    ready = bh1750fvi.I2C_DEFAULT_ADDR in devices
    ready &= sht30.I2C_DEFAULT_ADDR in devices
    ready &= scd40.I2C_DEFAULT_ADDR in devices
    ready &= qmp6988.I2C_DEFAULT_ADDR in devices
    return ready


# Escape hatch before we set up the Watchdog
button = machine.Pin(9, machine.Pin.IN, machine.Pin.PULL_UP)
if not button.value():
    print("Entering safe mode...")
    sys.exit()

# Setting up Watchdog. This requires boot-up to complete in 15 seconds
wdt = machine.WDT(timeout=15_000)
led = LED(machine.Pin(2, machine.Pin.OUT))

led.color(LED_CONFIG)
print("Loading configuration...")
with open("config.json") as f:
    cfg = json.load(f)

led.color(LED_NETWORK)
print("Connecting to network...")
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(cfg["wifi_ssid"], cfg["wifi_key"])
while not wifi.isconnected():
    time.sleep_ms(100)

led.color(LED_DEVICES)
print("Waiting for devices to become ready...")
i2c = machine.SoftI2C(sda=machine.Pin(1), scl=machine.Pin(0), freq=400000)
while not i2c_ready():
    time.sleep_ms(100)

loop = uasyncio.new_event_loop()
loop.set_exception_handler(error_handler)
loop.create_task(watchdog_feed())
loop.create_task(liveness_check())
loop.run_until_complete(main())
