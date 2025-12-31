import asyncio
import logging
import sys
from importlib.metadata import version
from CasambiBt import Casambi, discover
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.parse
import json
import dataclasses 

# Configuration
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8080

formatter = logging.Formatter(
    fmt="%(asctime)s %(name)-8s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
stream = logging.StreamHandler()
stream.setFormatter(formatter)
logging.getLogger().addHandler(stream)
_LOGGER = logging.getLogger(__name__)

@dataclasses.dataclass
class ConfiguredCasambiDevice:
    name: str 
    address: str 
    password: str

class CasambiService:
    def __init__(self):
        self.discovered_devices = []
        self.discovered_addresses = []
        self.configured_devices = []

    async def discover(self):
        print("Searching for Casambi devices ...")
        self.discovered_devices = await discover()

        self.discovered_addresses = []
        if not self.discovered_devices:
            print("No Casambi devices found")
        else: 
            for i, d in enumerate(self.discovered_devices):
                print(f"[{i}]\t{d.address}")
                self.discovered_addresses.append(d.address)

        return self.discovered_addresses

    def get_discovered_devices(self):
        return self.discovered_addresses

    def get_configured_devices(self):
        return self.configured_devices

    def get_configured_device(self, name):
        device = next((d for d in self.configured_devices if d.name == name), None)
        return device

    async def control_lights(self, name, on):
        ok = False
        config = self.get_configured_device(name)
        # find the BLEDevice
        device = next((d for d in self.discovered_devices if d.address == config.address), None)
        casa = Casambi()
        try:
            await casa.connect(device, config.password)
            if on:
                await casa.turnOn(None)
            else:
                await casa.setLevel(None, 0)
            ok = True
        except Exception as e:
            print("Exception: " + str(e))
        finally:
            await casa.disconnect()
        return ok

async def main() -> None:
    logLevel = logging.INFO
    if "-d" in sys.argv:
        logLevel = logging.DEBUG
        logging.getLogger("bleak").setLevel(logging.DEBUG)

    _LOGGER.setLevel(logLevel)
    logging.getLogger("CasambiBt").setLevel(logLevel)

    _LOGGER.debug(f"Bleak version: {version('bleak')}")
    _LOGGER.debug(f"Bleak retry connector version: {version('bleak-retry-connector')}")

    # Discover networks
    print("Searching...")
    devices = await discover()
    if not devices:
        print("No Casambi devices found")
        #sys.exit(1)
        
    for i, d in enumerate(devices):
        print(f"[{i}]\t{d.address}")

    #selection = int(input("Select network: "))

    #device = devices[selection]
    #pwd = input("Enter password: ")

    # Connect to the selected network
    #casa = Casambi()
    #try:
    #    await casa.connect(device, pwd)

        # Turn all lights on
    #    await casa.turnOn(None)
    #    await asyncio.sleep(5)

        # Turn all lights off
        # await casa.setLevel(None, 0)
        # await asyncio.sleep(1)

        # Print the state of all units
    #    for u in casa.units:
    #        print(u.__repr__())
    #finally:
    #    await casa.disconnect()

class MyHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, service_instance):
        super().__init__(server_address, RequestHandlerClass)
        self.service = service_instance

class MyRequestHandler(BaseHTTPRequestHandler):
    def address_string(self):
        """Override to avoid DNS reverse lookups which cause delays."""
        host, port = self.client_address[:2]
        return host

    def do_GET(self):
        """Handle HTTP GET requests."""
        
        # Parse the URL path and query parameters
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)

        print(f"Received GET request for: {path}")

        # Basic routing logic based on the path
        if path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Simple Casambi gateway to control lights with API calls</h1></body></html>")
            
        elif path == "/api/discover":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            try:
                devices = asyncio.run(self.server.service.discover())
                response_data = {"status": "success", "devices": devices}
            except Exception as e:
                response_data = {"status": "error", "message": str(e)}

            self.wfile.write(json.dumps(response_data, default=dataclasses.asdict).encode("utf-8"))
            
        elif path == "/api/devices":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "devices": self.server.service.get_discovered_devices()}

            self.wfile.write(json.dumps(response_data).encode("utf-8"))

        elif path == "/api/configured":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "devices": self.server.service.get_configured_devices()}

            self.wfile.write(json.dumps(response_data, default=dataclasses.asdict).encode("utf-8"))

        elif path == "/api/lights/on":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            name = query_params.get("name", [None])[0]
            device = self.server.service.get_configured_device(name)
            if device:
                asyncio.run(self.server.service.control_lights(name, True))
                response_data = {"status": "success", "device": device}
            else:
                response_data = {"status": "error", "message": "Device " + str(name) + " not found"}

            self.wfile.write(json.dumps(response_data, default=dataclasses.asdict).encode("utf-8"))

        elif path == "/api/lights/off":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            name = query_params.get("name", [None])[0]
            device = self.server.service.get_configured_device(name)
            if device:
                asyncio.run(self.server.service.control_lights(name, False))
                response_data = {"status": "success", "device": device}
            else:
                response_data = {"status": "error", "message": "Device " + str(name) + " not found"}

            self.wfile.write(json.dumps(response_data, default=dataclasses.asdict).encode("utf-8"))

        else:
            # 404 Not Found for any other path
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")

def run_server():
    """Starts the HTTP server."""
    casambi_service = CasambiService()
    casambi_service.configured_devices.append(ConfiguredCasambiDevice("flock", "5C:A4:92:4E:C3:C6", "Moooi1954"))
    casambi_service.configured_devices.append(ConfiguredCasambiDevice("stripe", "C6:AD:9D:4F:16:7E", "Reerinkris"))
    devices = asyncio.run(casambi_service.discover())

    server_address = (HOST, PORT)
    httpd = MyHTTPServer(server_address, MyRequestHandler, casambi_service)
    print(f"Server starting on http://{HOST}:{PORT}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("Server stopped.")


if __name__ == "__main__":
    #loop = asyncio.new_event_loop()
    #loop.run_until_complete(main())
    print("In " + __name__) 
    run_server()
    print("Server stopped in " + __name__) 

