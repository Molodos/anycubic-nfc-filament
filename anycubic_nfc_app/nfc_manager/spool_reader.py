import json
from typing import Any, Optional

from .nfc_readers import CardData, READERS_NFC


class SpoolData(CardData):
    """
    Spool data
    """

    SKUS: dict[str, str] = {
        "PLA": "AHPLBK-101",
        "PLA+": "AHPLPBK-102",  # Material name not recognized by slicer (recognized as PLA)
        "PLA High Speed": "AHHSBK-102",
        "PLA Matte": "HYGBK-101",  # SKU not recognized by slicer
        "PLA Silk": "HSCWH-101",  # SKU not recognized by slicer
        "PETG": "HPEBK-103",  # SKU not recognized by slicer
        "ASA": "HASBK-101",  # SKU not recognized by slicer
        "ABS": "HABBK-102",  # SKU not recognized by slicer
        "TPU": "HTPBK-101",  # SKU not recognized by slicer
        "PLA Luminous": "HFGBL-101"  # SKU not recognized by slicer
    }
    SKU_PREFIXES: dict[str, str] = {
        "AHPL": "PLA",
        "AHPLP": "PLA+",
        "AHHS": "PLA High Speed",
        "HYG": "PLA Matte",
        "HSC": "PLA Silk",
        "HPE": "PETG",
        "HAS": "ASA",
        "HAB": "ABS",
        "HTP": "TPU",
        "HFG": "PLA Luminous"
    }

    def __init__(self, spool_specs: Optional[dict[str, Any]] = None):
        """
        Create a spool data object
        :param spool_specs: Optionally, add spool specs directly
        """
        super().__init__(page_count=0x2d)
        if spool_specs:
            self.set_spool_specs(spool_specs)

    @classmethod
    def get_available_filament_types(cls) -> list[str]:
        """
        Get a list of available filament types
        :return: List of filament types
        """
        return list(cls.SKUS.keys())

    def _write_byte(self, page: int, index: int, data: int) -> None:
        """
        Write a byte
        :param page: Page in the data
        :param index: Index on the page
        :param data: Byte to write
        """
        page_data = bytearray(self.pages[page])
        page_data[index] = data
        self.pages[page] = bytes(page_data)

    def _read_byte(self, page: int, index: int) -> int:
        """
        Write a byte
        :param page: Page in the data
        :param index: Index on the page
        :return: read byte
        """
        return bytearray(self.pages[page])[index]

    def _write_bytes(self, page: int, index: int, data: int) -> None:
        """
        Write two bytes (big endian)
        :param page: Page in the data
        :param index: Index on the page
        :param data: Bytes to write
        """
        low_byte = data % 256
        high_byte = data // 256
        self._write_byte(page, index, low_byte)
        if index == 3:
            self._write_byte(page + 1, 0, high_byte)
        else:
            self._write_byte(page, index + 1, high_byte)

    def _read_bytes(self, page: int, index: int) -> int:
        """
        Read two bytes (big endian)
        :param page: Page in the data
        :param index: Index on the page
        :return: Read bytes
        """
        low_byte: int = self._read_byte(page, index)
        if index == 3:
            high_byte = self._read_byte(page + 1, 0)
        else:
            high_byte = self._read_byte(page, index + 1)
        return high_byte * 256 + low_byte

    def read_uid(self) -> str:
        """
        Read the tags uid
        :return: The hex uid
        """
        a = self._read_byte(0, 0)
        b = self._read_byte(0, 1)
        c = self._read_byte(0, 2)
        d = self._read_byte(1, 0)
        e = self._read_byte(1, 1)
        f = self._read_byte(1, 2)
        g = self._read_byte(1, 3)
        uid: str = f"{a:02x}{b:02x}{c:02x}{d:02x}{e:02x}{f:02x}{g:02x}"
        return uid

    def _write_color(self, page: int, hex_color: str) -> None:
        """
        Write a hex color (abgr)
        :param page: Page in the data
        :param hex_color: The hex color to write (with #)
        """
        if not hex_color:
            return
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        self._write_byte(page, 0, 255)
        self._write_byte(page, 1, b)
        self._write_byte(page, 2, g)
        self._write_byte(page, 3, r)

    def _read_color(self, page: int) -> str:
        """
        Read a color (abgr)
        :param page: Page in the data
        :return: The hex color code
        """
        a = self._read_byte(page, 0)
        b = self._read_byte(page, 1)
        g = self._read_byte(page, 2)
        r = self._read_byte(page, 3)
        color: str = f"#{r:02x}{g:02x}{b:02x}"
        if color == "#000000" and a == 0:
            return ""
        return color

    def _write_string(self, page: int, data: str) -> None:
        """
        Write a string (max 20 characters)
        :param page: Page in the data
        :param data: String to write
        """
        for i in range(min(len(data), 20)):
            self._write_byte(page + i // 4, i % 4, ord(data[i]))

    def _read_string(self, page) -> str:
        """
        Read a string (max 20 characters)
        :param page: Page in the data
        :return: The read string
        """
        data: str = ""
        i = 0
        byte = self._read_byte(page, i)
        while byte > 0:
            data += chr(byte)
            if len(data) >= 20:
                break
            i += 1
            if i == 4:
                i = 0
                page += 1
            byte = self._read_byte(page, i)
        return data

    def _set_format_version(self, version: int) -> None:
        """
        Set the format version of the tag
        :param version: Version (1 or 2 (adds print speed))
        """
        if version == 1:
            self._write_byte(0x04, 2, 0x64)
        elif version == 2:
            self._write_byte(0x04, 2, 0x65)

    def set_spool_specs(self, spool_specs: dict[str, Any]) -> None:
        """
        Set the spool specs data
        :param spool_specs: Spool specs JSON
        """
        # Static
        self._write_byte(0x04, 0, 0x7b)
        self._write_byte(0x27, 3, 0x4d)  # Custom spool marker
        self._set_format_version(2)

        # SKU, manufacturer and type
        self._write_string(0x05, self.SKUS.get(spool_specs["type"], "AHPLBK-101"))
        self._write_string(0x0a, spool_specs.get("manufacturer", "AC"))
        self._write_string(0x0f, spool_specs["type"])

        # Color
        self._write_color(0x14, spool_specs["color"])

        # Print speed (optional)
        self._write_bytes(0x17, 0, spool_specs["range_a"].get("speed_min", 0))
        self._write_bytes(0x17, 2, spool_specs["range_a"].get("speed_max", 0))

        # Nozzle temp
        self._write_bytes(0x18, 0, spool_specs["range_a"]["nozzle_min"])
        self._write_bytes(0x18, 2, spool_specs["range_a"]["nozzle_max"])

        # Additional print speed ranges (optional)
        if "range_b" in spool_specs:
            self._write_bytes(0x19, 0, spool_specs["range_b"].get("speed_min", 0))
            self._write_bytes(0x19, 2, spool_specs["range_b"].get("speed_max", 0))
            self._write_bytes(0x1a, 0, spool_specs["range_b"].get("nozzle_min", 0))
            self._write_bytes(0x1a, 2, spool_specs["range_b"].get("nozzle_max", 0))
        if "range_c" in spool_specs:
            self._write_bytes(0x1b, 0, spool_specs["range_c"].get("speed_min", 0))
            self._write_bytes(0x1b, 2, spool_specs["range_c"].get("speed_max", 0))
            self._write_bytes(0x1c, 0, spool_specs["range_c"].get("nozzle_min", 0))
            self._write_bytes(0x1c, 2, spool_specs["range_c"].get("nozzle_max", 0))

        # Bed temp
        self._write_bytes(0x1d, 0, spool_specs["bed_min"])
        self._write_bytes(0x1d, 2, spool_specs["bed_max"])

        # Diameter
        self._write_bytes(0x1e, 0, round(spool_specs["diameter"] * 100))

        # Length
        self._write_bytes(0x1e, 2, spool_specs["length"])

        # Weight
        self._write_bytes(0x1f, 0, spool_specs["weight"])

    def get_spool_specs(self) -> dict[str, Any]:
        """
        Get the spool specs data
        :return: Spool specs JSON
        """
        # Read sku and calculate type from the longest matching prefix
        sku: str = self._read_string(0x05)
        possible_prefixes: list[str] = []
        for p in self.SKU_PREFIXES.keys():
            if sku.startswith(p):
                possible_prefixes.append(p)
        possible_prefixes.sort(key=len, reverse=True)
        read_type: str = self._read_string(0x0f)
        sku_type: str = self.SKU_PREFIXES[possible_prefixes[0]] if possible_prefixes else read_type
        possible_types: list[str] = self.get_available_filament_types()
        if sku_type not in possible_types:
            sku_type = possible_types[0]

        # Read specs
        spool_specs: dict[str, Any] = {
            "uid": self.read_uid(),
            "type": sku_type,
            "manufacturer": self._read_string(0x0a),
            "color": self._read_color(0x14),
            "range_a": {
                "speed_min": self._read_bytes(0x17, 0),
                "speed_max": self._read_bytes(0x17, 2),
                "nozzle_min": self._read_bytes(0x18, 0),
                "nozzle_max": self._read_bytes(0x18, 2),
            },
            "range_b": {
                "speed_min": self._read_bytes(0x19, 0),
                "speed_max": self._read_bytes(0x19, 2),
                "nozzle_min": self._read_bytes(0x1a, 0),
                "nozzle_max": self._read_bytes(0x1a, 2)
            },
            "range_c": {
                "speed_min": self._read_bytes(0x1b, 0),
                "speed_max": self._read_bytes(0x1b, 2),
                "nozzle_min": self._read_bytes(0x1c, 0),
                "nozzle_max": self._read_bytes(0x1c, 2)
            },
            "bed_min": self._read_bytes(0x1d, 0),
            "bed_max": self._read_bytes(0x1d, 2),
            "diameter": self._read_bytes(0x1e, 0) / 100,
            "length": self._read_bytes(0x1e, 2),
            "weight": self._read_bytes(0x1f, 0),
            "raw": {  # Raw data for research purposes
                "sku": sku,
                "type": read_type,
                "is_custom": self._read_bytes(0x27, 3) == 0x4d
            },
        }

        # Return
        return spool_specs

    def dump(self) -> str:
        """
        Dump the data
        :return: The dump as string
        """
        return json.dumps(self.get_spool_specs(), indent=4)


class SpoolReader:
    """
    Reader/writer for Anycubic filament spools
    """

    def __init__(self):
        """
        Initialize card reader
        """
        self.reader: READERS_NFC = READERS_NFC()

    def get_connection_state(self) -> bool:
        """
        Get the current connection state
        :return: True if connected else False
        """
        return self.reader.reader is not None

    def cancel_wait_for_tag(self) -> None:
        """
        Cancel the waiting for a tag
        """
        self.reader.waiting_for_tag = False

    @classmethod
    def get_available_filament_types(cls) -> list[str]:
        """
        Get a list of available filament types
        :return: List of filament types
        """
        return SpoolData.get_available_filament_types()

    def read_spool(self) -> Optional[dict[str, Any]]:
        """
        Wait for a spool, read it and return its data
        :return: JSON data of the spool on success else None
        """
        card_data: Optional[CardData] = self.reader.read_card()
        if not card_data:
            return None
        spool_data: SpoolData = SpoolData()
        spool_data.pages = card_data.pages
        return spool_data.get_spool_specs()

    def read_spool_raw(self) -> tuple[Optional[str], Optional[str]]:
        """
        Wait for a spool, read it and return its raw data (+ interpretation if possible)
        :return: Raw data of the nfc tag
        """
        card_data: Optional[CardData] = self.reader.read_card()
        if not card_data:
            return None, None
        raw_data: str = card_data.dump()
        try:
            spool_data: SpoolData = SpoolData()
            spool_data.pages = card_data.pages
            interpretation: str = json.dumps(spool_data.get_spool_specs(), indent=4)
            return spool_data.read_uid(), f"{raw_data}\n\n{interpretation}"
        except:
            return 14*"0", raw_data

    def write_spool(self, spool_specs: dict[str, Any]) -> bool:
        """
        Wait for a spool and write the data
        :param spool_specs: JSON spool data
        :return: Success state
        """
        spool_data: SpoolData = SpoolData()
        spool_data.set_spool_specs(spool_specs)
        return self.reader.write_card(spool_data)
