# Copyright (c) 2022 Sebastian Wicki
# SPDX-License-Identifier: MIT
"""
I2C-based driver for the SHT temperature and humidity sensor.
"""
from micropython import const
from time import sleep_us
from ustruct import pack, unpack_from

from checksum import crc8

I2C_DEFAULT_ADDR = const(0x44)

_SHT30_CMD_MEASURE_REP_HI_CS_EN = const(0x2c06)
_SHT30_CMD_RESET = const(0x30a2)
_SHT30_CMD_STATUS = const(0xf32d)

_SHT30_STATUS_MASK_ALL = const(0b1010_1100_0001_0011)
_SHT30_STATUS_DEFAULT = const(0b1000_0000_0001_0000)

_SHT30_FRAME_LEN = const(3)
_SHT30_DATA_LEN = const(2)


class SHT30:
    def __init__(self, i2c, *, addr=I2C_DEFAULT_ADDR):
        self.i2c = i2c
        self.addr = addr
        self.reset()

    def reset(self):
        """
        Performs a soft reset of the device and waits for it to enter idle state.
        """
        self._write_cmd(_SHT30_CMD_RESET)
        # waits 3x500us (max. t_SR) for device to become ready
        for _ in range(3):
            sleep_us(500)
            status = self._read_cmd(_SHT30_CMD_STATUS, 1)
            if (status[0] & _SHT30_STATUS_MASK_ALL == _SHT30_STATUS_DEFAULT):
                return
        raise ValueError("device not found")

    def measure(self):
        """
        Returns the temperature (in °C) and humidity (in %)  as a 2-tuple in the
        form of:
        (temperature, humidity)
        """
        s_t, s_rh = self._read_cmd(_SHT30_CMD_MEASURE_REP_HI_CS_EN, 2)
        if s_t == 0 and s_rh == 0:
            raise RuntimeError("device not ready")
        t = -45 + ((s_t * 175) / 0xffff)
        rh = (s_rh * 100) / 0xffff
        return t, rh

    def _write_cmd(self, cmd):
        self.i2c.writeto(self.addr, pack(">H", cmd))

    def _read_cmd(self, cmd, nvalues=0):
        buf = memoryview(bytearray(nvalues * _SHT30_FRAME_LEN))
        self.i2c.readfrom_mem_into(self.addr, cmd, buf, addrsize=16)

        offset = 0
        values = []
        for _ in range(nvalues):
            value, crc = unpack_from(">HB", buf, offset)
            if crc != crc8(buf[offset:offset+_SHT30_DATA_LEN]):
                raise Exception("checksum error")
            values.append(value)
            offset += _SHT30_FRAME_LEN

        return values
