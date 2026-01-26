# This is a custom mock of the spidev library, created to allow this application
# to run on a non-Raspberry Pi machine (like Windows) for development.
# It provides the minimal set of methods required by the MFRC522 library.

class SpiDev:
    """A mock SpiDev class."""
    def open(self, bus, device):
        """Mocks opening the SPI bus. Does nothing."""
        print(f"Mock SpiDev: Opening SPI bus {bus}, device {device}")
        pass

    def xfer2(self, data):
        """
        Mocks transferring data. The MFRC522 library expects a list of integers
        (bytes) in response. Returning a list of zeros of the same length as the
        input data is a safe default that prevents crashes.
        """
        # print(f"Mock SpiDev: Transferring {len(data)} bytes")
        return [0] * len(data)

    def close(self):
        """Mocks closing the SPI bus. Does nothing."""
        print("Mock SpiDev: Closing SPI bus")
        pass
