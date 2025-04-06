import threading
import time
from typing import List, Optional

from smartcard.CardConnection import CardConnection
from smartcard.System import readers
from smartcard.reader.Reader import Reader


class CardData:
    """
    Card data
    """

    def __init__(self, page_count: int = 0x2d):
        """
        Create card data object
        :param page_count: Number of pages
        """
        self.pages: list[bytes] = page_count * [b"\x00\x00\x00\x00"]

    def dump(self) -> str:
        """
        Dump the data
        :return: The dump as string
        """
        pages: list[str] = []
        for page, page_data in enumerate(self.pages):
            hex_data: list[str] = [f"{x:02x}" for x in page_data]
            pages.append(f"[Page {page:02x}] {':'.join(hex_data)}")
        return "\n".join(pages)


class READERS_NFC:
    """
    A list of supported nfc readers
    """

    # List of supported readers (each one has a list of strings that need to be part of its name)
    supported_readers: list[list[str]] = [
        ["acr122"],
        ["acr1252", "picc"] #The ACR1252 will be recognised as two readers one as PICC one as SAM (that one won`t work)
    ]
    preferred_reader: Optional[str] = None

    def __init__(self):
        """
        Create an instance
        """
        self.waiting_for_tag: bool = False
        self.reader: Optional[Reader] = self._get_reader()
        checker_thread = threading.Thread(target=self.update_connection_state)
        checker_thread.daemon = True
        checker_thread.start()

    def update_connection_state(self) -> None:
        """
        Update the connection state
        """
        while True:
            new_reader: Optional[Reader] = self._get_reader()
            if str(self.reader) != str(new_reader):
                self.reader = new_reader
            time.sleep(1)

    @classmethod
    def _get_reader(cls) -> Optional[Reader]:
        """
        Get a connection to the reader device
        :return: Reader connection
        """
        available_readers: list[Reader] = readers()
        found_reader: Optional[Reader] = None

        # Check preferred reader
        if cls.preferred_reader:
            for reader in available_readers:
                if cls.preferred_reader.lower() in reader.name.lower():
                    found_reader = reader

        # Check supported readers
        if not found_reader:
            for reader in available_readers:
                # There are multiple supported readers
                for parts in cls.supported_readers:
                    is_supported = True
                    # Each supported reader has multiple parts that the name needs to contain
                    for part in parts:
                        if part.lower() not in reader.name.lower():
                            is_supported = False
                    if is_supported:
                        found_reader = reader
        return found_reader

    @classmethod
    def _read_page(cls, connection: CardConnection, page: int) -> Optional[bytes]:
        """
        Read from page on card
        :param connection: Connection to the card
        :param page: Page number
        :return: The read data (4 bytes)
        """
        read_page_command: list[int] = [0xFF, 0xB0, 0x00, page, 0x04]
        response, sw1, sw2 = connection.transmit(read_page_command)
        if sw1 == 0x90 and sw2 == 0x00:
            return response
        else:
            return None

    @classmethod
    def _write_page(cls, connection: CardConnection, page: int, data: bytes) -> bool:
        """
        Write to page on card
        :param connection: Connection to the card
        :param page: Page number
        :param data: Data to write
        :return: Success state
        """
        write_page_command: List[int] = [0xFF, 0xD6, 0x00, page, 0x04] + list(data)
        response, sw1, sw2 = connection.transmit(write_page_command)
        if sw1 == 0x90 and sw2 == 0x00:
            return True
        else:
            return False

    def _wait_for_card(self) -> Optional[CardConnection]:
        """
        Wait for a card to be found
        :return: The connection to the card (if possible)
        """
        if not self.reader:
            return None
        connection: CardConnection = self.reader.createConnection()
        self.waiting_for_tag = True
        while self.waiting_for_tag:
            try:
                connection.connect()
                self.waiting_for_tag = False
                return connection
            except Exception:
                time.sleep(0.5)

    def read_card(self, page_count: int = 0x2d) -> Optional[CardData]:
        """
        Read data from card
        :param page_count: Number of pages on the card
        :return: The data of the card on success else None
        """
        connection: CardConnection = self._wait_for_card()
        if not connection:
            return None
        data: CardData = CardData(page_count)
        for page in range(0, page_count):
            d: bytes = self._read_page(connection, page)
            if d is None:
                print(f"[Error] Failed to read page {page}. Reading cancelled.")
                time.sleep(3)
                return None
            else:
                data.pages[page] = d
        return data

    def write_card(self, card_data: CardData, page_count: int = 0x2d) -> bool:
        """
        Write data to card
        :param card_data: Data to write
        :param page_count: Number of pages on the card
        :return: Success state
        """
        connection: CardConnection = self._wait_for_card()
        if not connection:
            return False
        for page, page_data in enumerate(card_data.pages):
            # Don't write to management data pages
            if 0x03 < page < page_count - 5:
                if not self._write_page(connection, page, page_data):
                    return False
        return True
