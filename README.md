# micropython-m5stamp-c3u

This repository contains examples for the
[M5Stamp C3U](https://docs.m5stack.com/en/core/stamp_c3u) development board.

All drivers are written in pure [Micropython](https://micropython.org/) and are
intended to be used with the generic Micropython build for ESP32-C3-USB-based
boards.

Some of the modules in this repository make use of [`micropython.const`][const]
to optimize memory usage when deployed in [pre-compiled bytecode][mpy] form.

[const]: http://docs.micropython.org/en/latest/library/micropython.html#micropython.const
[mpy]: http://docs.micropython.org/en/latest/reference/mpyfiles.html

## Getting Started with Micropython

This section guides you through the steps to flash Micropython to the M5Stamp
C3U board.

### Enter Download Mode

To enter the download mode, press and hold the center button (G9) under a
power failure condition. To achieve this, *either* hold the center
button while pressing reset and then release the center button,
*or* disconnect the USB cable and then hold the center button while
connecting the USB cable, and then release the center button.

If successful, the M5Stamp will present a USB CDC ACM device on your host.

### Flash Micropython Firmware

Download the [ESP32-C3 with USB](https://micropython.org/download/esp32c3-usb/)
Micropython port for the M5Stamp C3U.

While the device is in download mode, flash Micropython to the M5Stamp C3U
as follows:

```
esptool.py --chip esp32c3 --port /dev/ttyACM0 --baud 460800 \
    write_flash -z 0x0 esp32c3-usb-20220618-v1.19.1.bin
```

Reset the device and you will be able to use the Micropython console via the
USB CDC serial device.

## Examples

### LED and Button

This example changes the LED color each time the center button is pressed.

```python
import machine, neopixel, random, time

button = machine.Pin(9, machine.Pin.IN, machine.Pin.PULL_UP)
led = neopixel.NeoPixel(machine.Pin(2, machine.Pin.OUT), 1)

led.fill((0, 255, 200))
led.write()

while True:
  if button.value() == 0:
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    led.fill((r, g, b))
    led.write()
  time.sleep_ms(50)
```

### Grove Peripherals

The following example assumes a Grove connector is soldered to the board on
Port A (pins G0/G1/5V/GND). It assumes the following units are all connected
to the same I2C bus via the Grove Hub:

 - [TVOC/eCO2 Unit](https://docs.m5stack.com/en/unit/tvoc):
   `SGP30` (indoor air quality, I2C `0x44`)
 - [ENV III Unit](https://docs.m5stack.com/en/unit/envIII):
   `SHT30` (temperature and humidity, I2C `0x44`), `QMP6988` (absolute air pressure, I2C `0x70`)
 - [DLight Unit](https://docs.m5stack.com/en/unit/dlight):
   `BH1750FVI` (ambient light, I2C `0x23`)

```python
import machine
import uasyncio

import bh1750fvi
import sht30
import sgp30
import qmp6988

i2c = machine.SoftI2C(sda=machine.Pin(1), scl=machine.Pin(0), freq=400000)

async def main():
  dlx = bh1750fvi.BH1750FVI(i2c)
  rht = sht30.SHT30(i2c)
  voc = sgp30.SGP30(i2c)
  prt = qmp6988.QMP6988(i2c)

  await voc.start()

  while True:
    light = dlx.measure()
    print("Ambient Light: {}lx".format(light))

    temp, humidity = rht.measure()
    print("Temp/Humidity: {}°C/{}%".format(temp, humidity))

    voc.set_absolute_humidity(sgp30.absolute_humidity(temp, humidity))
    eco2, tvoc = voc.measure()
    print("eCO2/TVOC: {}ppm/{}ppb".format(eco2, tvoc))

    temp, pressure = prt.measure()
    print("Temp/Pressure: {}°C/{}Pa".format(temp, pressure))

    await uasyncio.sleep(1)

uasyncio.run(main())
```

*Note:* To install the required Micropython drivers using
[`mpremote`](https://pypi.org/project/mpremote/), copy the `lib/` folder to your
device as follows:

```console
$ mpremote a0 cp -r lib :
```

## Contributing

Contributions are welcome! Please read and follow the
[Code of Conduct](CODE_OF_CONDUCT.md) and make sure to acknowledge the
[Developer Certificate of Origin](https://developercertificate.org/) when
contributing.
