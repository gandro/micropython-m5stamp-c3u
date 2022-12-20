# Copyright (c) 2022 Sebastian Wicki
# SPDX-License-Identifier: MIT

import io
import json
import socket
import ssl
import uasyncio


class HTTPResponse:
    def __init__(self, status, reason):
        self.status = status
        self.reason = reason
        self.body = b""


async def request(host, port, method, path, *, raw=None, obj=None, headers={}, use_ssl=False):
    ai = socket.getaddrinfo(host, port, socket.SOCK_STREAM)
    s = socket.socket()
    s.connect(ai[0][-1])
    s.setblocking(False)
    default_port = 80
    if use_ssl:
        default_port = 443
        s = ssl.wrap_socket(s, do_handshake=False)

    host = host
    port = b":{}".format(port) if port != default_port else b""
    r = uasyncio.StreamReader(s)
    w = uasyncio.StreamWriter(s)

    try:
        w.write(method)
        w.write(b" ")
        w.write(path)
        w.write(b" ")
        w.write("HTTP/1.0")
        w.write(b"\r\n")

        # Request headers
        if not "Host" in headers:
            w.write(b"Host:")
            w.write(host)
            if port:
                w.write(port)
            w.write(b"\r\n")
        for key in headers:
            w.write(key)
            w.write(b": ")
            w.write(headers[key])
            w.write(b"\r\n")
        if obj is not None:
            w.write(b"Content-Type:application/json\r\n")
            buf = io.BytesIO()
            json.dump(obj, buf)
            raw = buf.getvalue()
        if raw:
            w.write(b"Content-Length:")
            w.write(b"{}\r\n".format(len(raw)))
        w.write(b"\r\n")

        # Request data
        if raw:
            w.write(raw)
        await w.drain()

        # Response headers
        line = await r.readline()
        status = line.split(None, 2)
        if len(status) < 2:
            raise ValueError("invalid format")
        code = int(status[1])
        reason = status[2].rstrip()
        resp = HTTPResponse(code, reason)
        length = 0
        while line and line != b"\r\n":
            if line.startswith(b"Content-Length:"):
                length = int(line.split(b":", 1)[1])
            if line.startswith(b"Transfer-Encoding"):
                raise NotImplementedError(line)
            line = await r.readline()

        # Response data
        if length:
            resp.body = await r.readexactly(length)
        return resp
    finally:
        await w.wait_closed()


class Sensor:
    def __init__(self, name, unit_of_measurement=None, device_class=None, friendly_name=None):
        self.name = name
        self.attrs = {}
        if unit_of_measurement:
            self.attrs["unit_of_measurement"] = unit_of_measurement
        if device_class:
            self.attrs["device_class"] = device_class
        if friendly_name:
            self.attrs["friendly_name"] = friendly_name


class HomeAssistant:
    def __init__(self, host, port, use_ssl=False, token=None):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.headers = {}
        if token:
            self.headers["Authorization"] = "Bearer " + token

    async def submit(self, sensor, state):
        obj = {"state": state}
        if sensor.attrs:
            obj["attributes"] = sensor.attrs

        resp = await request(
            self.host,
            self.port,
            "POST",
            "/api/states/sensor." + sensor.name,
            obj=obj,
            headers=self.headers,
            use_ssl=self.use_ssl
        )
        if resp.status not in [200, 201]:
            raise RuntimeError(resp.body)
