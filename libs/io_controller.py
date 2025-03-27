from ast import arg
import serial
import threading
import time
import enum
from typing import Callable

from PyQt5.QtCore import pyqtSignal, QObject


class OutPorts(enum.Enum):
    All = 0
    Out_1 = 1
    Out_2 = 2
    Out_3 = 3
    Out_4 = 4
    Out_5 = 5
    Out_6 = 6
    Out_7 = 7
    Out_8 = 8


class InPorts(enum.Enum):
    All = 0
    In_1 = 1
    In_2 = 2
    In_3 = 3
    In_4 = 4
    In_5 = 5
    In_6 = 6
    In_7 = 7
    In_8 = 8


class PortState(enum.Enum):
    Off = 0
    On = 1


class IOType(enum.Enum):
    FourPorts = 0
    EightPorts = 1


class IODataReceivedEventArgs:
    def __init__(self, command: InPorts, state: PortState):
        self.command = command
        self.state = state


class IOController(QObject):
    inputSignal = pyqtSignal(InPorts, PortState)

    def __init__(self, com: str, baud: int = 9600, io_type=IOType.FourPorts):
        super().__init__()
        self.port_name = com
        self.baud_rate = baud
        self.io_type = io_type
        self.received_bytes_threshold = 3
        self.stored_byte_in = 0
        self.serial_port = None
        self.data_received_callbacks = []
        self.running = False

        if self.io_type == IOType.FourPorts:
            self.port_out = [0xFF, 0x01, 0x02, 0x04, 0x08]
            self.port_in = [0x00, 0x01, 0x02, 0x04, 0x08]
        else:
            self.port_out = [0xFF, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]
            self.port_in = [0x00, 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01]

        operation: Callable[[IODataReceivedEventArgs], None] = self.callback
        self.add_data_received_callback(operation)

    def add_data_received_callback(
        self, callback: Callable[[object, IODataReceivedEventArgs], None]
    ):
        """Add a callback function that will be called when data is received"""
        self.data_received_callbacks.append(callback)

    def callback(self, args: IODataReceivedEventArgs):
        print("callback received")
        self.inputSignal.emit(args.command, args.state)

    def is_open(self) -> bool:
        return self.serial_port is not None and self.serial_port.is_open

    def open(self) -> bool:
        """Open the serial connection to the I/O controller"""
        try:
            self.serial_port = serial.Serial(
                port=self.port_name, baudrate=self.baud_rate, timeout=1
            )

            print(f"I/O Controller Connected {self.port_name}")

            # Start a thread to read from the serial port
            self.running = True
            self.read_thread = threading.Thread(target=self.read_loop)
            self.read_thread.start()

            return True
        except Exception as ex:
            print(f"Error opening port: {ex}")
            return False

    def close(self):
        """Close the serial connection"""
        try:
            if self.serial_port is not None:
                self.serial_port.close()
                print("Closed IO Controller")
            return True
        except Exception as e:
            print(f"Failed to close IO Controller")
            return False

    def write_out(self, command: OutPorts, state: PortState) -> bool:
        """Send a command to the output port"""
        result = False

        if not self.is_open():
            print("Cannot send command - port is not open")
            return result

        # Check if trying to use ports > 4 when in FourPorts mode
        if self.io_type == IOType.FourPorts and command.value > OutPorts.Out_4.value:
            print(f"Cannot use {command} with Four Ports mode")
            return result

        try:
            bytes_to_send = bytearray(
                [0x98, self.port_out[command.value], state.value, 0x99]
            )
            print(f"Sending raw data: {' '.join([f'{b:02X}' for b in bytes_to_send])}")
            self.serial_port.write(bytes_to_send)
            self.serial_port.flush()  # Đảm bảo dữ liệu được gửi đi
            print(f"I/O Controller Send {command}, State {state}")
            result = True
        except Exception as ex:
            print(f"Error writing to port: {ex}")

        return result

    def read_loop(self):
        """Read continuously from the serial port in a separate thread"""
        while self.running and self.is_open():
            try:
                # Check if there's data available to read
                if (
                    self.serial_port.in_waiting > 0
                ):  # Thay đổi để đọc bất kỳ dữ liệu nào
                    # Read available bytes
                    buffer = self.serial_port.read(self.serial_port.in_waiting)
                    print(
                        f"Raw data received: {' '.join([f'{b:02X}' for b in buffer])}"
                    )
                    if len(buffer) >= 3:  # Chỉ xử lý nếu đủ 3 byte
                        self.process_in_data(buffer)

                # Small delay to prevent high CPU usage
                time.sleep(0.01)
            except Exception as ex:
                print(f"Error reading from port: {ex}")
                time.sleep(1)  # Longer delay after error
            """Read continuously from the serial port in a separate thread"""

            while self.running and self.is_open():
                try:
                    # Check if there's data available to read
                    if self.serial_port.in_waiting >= self.received_bytes_threshold:
                        # Read available bytes
                        buffer = self.serial_port.read(self.serial_port.in_waiting)
                        self.process_in_data(buffer)

                        # Print received bytes for debugging
                        debug_str = "Received bytes: " + " ".join(
                            [f"{b:02X}" for b in buffer]
                        )
                        print(debug_str)

                    # Small delay to prevent high CPU usage
                    time.sleep(0.1)
                except Exception as ex:
                    print(f"Error reading from port: {ex}")
                    time.sleep(1)  # Longer delay after error

    def process_in_data(self, buffer: bytes):
        """Process incoming data from the I/O controller"""
        if len(buffer) < 3:
            return

        # Calculate the difference between current and stored byte
        temp = (
            self.stored_byte_in - buffer[1]
            if buffer[1] < self.stored_byte_in
            else buffer[1] - self.stored_byte_in
        )

        # Find the command based on the port_in mapping
        try:
            command_index = self.port_in.index(temp)
            command = InPorts(command_index)
        except ValueError:
            # If the byte is not found in port_in
            print(f"Unknown input byte: {temp:02X}")
            return

        # Determine state based on whether value increased or decreased
        state = PortState.On if buffer[1] > self.stored_byte_in else PortState.Off

        # Update stored byte
        self.stored_byte_in = buffer[1]

        print(f"I/O Controller Received {command}, State {state}")

        # Notify callbacks
        event_args = IODataReceivedEventArgs(command, state)
        for callback in self.data_received_callbacks:
            callback(event_args)


if __name__ == "__main__":
    lcp = IOController(com="COM10", baud=19200)
    print(lcp.open())
    lcp.write_out(OutPorts.Out_1, PortState.On)
    time.sleep(3)
    lcp.write_out(OutPorts.Out_1, PortState.Off)

    # lcp.close()
