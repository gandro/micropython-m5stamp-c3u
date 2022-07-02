import machine, neopixel, time, random

# button config
button = machine.Pin(9, machine.Pin.IN, machine.Pin.PULL_UP)

np = neopixel.NeoPixel(machine.Pin(2, machine.Pin.OUT), 1)

while True:
    time.sleep(0.6)
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    np.fill((r, g, b))
    np.write()
