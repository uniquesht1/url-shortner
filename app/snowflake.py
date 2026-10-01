import time


class SnowflakeGenerator:
    """
    Twitter-style 64-bit Snowflake ID Generator.

    Structure of the 64-bit integer:
    +-------------------------------------------------------------------+
    | timestamp (ms) | datacenter_id | machine_id |  sequence (0-4095)  |
    |    (42 bits)   |    (5 bits)   |  (5 bits)  |      (12 bits)      |
    +-------------------------------------------------------------------+
    <- shifted by 22 -><- shift 17 -><- shift 12 -><- bits 0 to 11 ---->
    """

    def __init__(self, datacenter_id: int, machine_id: int):
        # 5 bits allow values from 0 to 31 (2^5 - 1 = 31)
        if not 0 <= datacenter_id <= 31:
            raise ValueError("datacenter_id must be between 0 and 31 (5 bits max)")

        if not 0 <= machine_id <= 31:
            raise ValueError("machine_id must be between 0 and 31 (5 bits max)")

        self.datacenter_id = datacenter_id
        self.machine_id = machine_id

        # 12-bit counter (0 to 4095) to allow 4096 IDs per millisecond
        self.sequence = 0
        self.last_timestamp = -1



    def _current_timestamp(self) -> int:
        """Returns the current Unix time in milliseconds."""
        return int(time.time() * 1000)



    def _wait_next_millis(self, last_timestamp: int) -> int:
        """Busy-waits until the clock advances to the next millisecond."""
        timestamp = self._current_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._current_timestamp()
        return timestamp



    def next_id(self) -> int:
        """Generates the next unique 64-bit Snowflake ID."""
        timestamp = self._current_timestamp()

        # Clock drift guard: system time should never go backwards
        if timestamp < self.last_timestamp:
            raise RuntimeError("Clock moved backwards. Refusing to generate ID.")

        if timestamp == self.last_timestamp:
            # Same millisecond: increment the sequence counter
            self.sequence += 1

            # 12 bits max is 4095. If exceeded, wait for the next millisecond
            if self.sequence > 4095:
                timestamp = self._wait_next_millis(self.last_timestamp)
                self.sequence = 0
        else:
            # New millisecond: reset sequence counter to 0
            self.sequence = 0

        self.last_timestamp = timestamp

        # Bitwise packing into a single 64-bit integer
        return (
            (timestamp << 22)
            | (self.datacenter_id << 17)
            | (self.machine_id << 12)
            | self.sequence
        )
