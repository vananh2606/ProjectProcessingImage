import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import enum
import time
import threading
from typing import Callable, List, Optional


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


class IOController:
    def __init__(
        self,
        port_name: str,
        baud_rate: int = 19200,
        io_type: IOType = IOType.EightPorts,
    ):
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.io_type = io_type
        self.data_bits = 8
        self.parity = serial.PARITY_NONE
        self.stop_bits = serial.STOPBITS_ONE
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

    def is_open(self) -> bool:
        return self.serial_port is not None and self.serial_port.is_open

    def add_data_received_callback(
        self, callback: Callable[[object, IODataReceivedEventArgs], None]
    ):
        """Add a callback function that will be called when data is received"""
        self.data_received_callbacks.append(callback)

    def open(self) -> bool:
        """Open the serial connection to the I/O controller"""
        try:
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=self.baud_rate,
                bytesize=self.data_bits,
                parity=self.parity,
                stopbits=self.stop_bits,
                timeout=1,
            )
            self.write_line(f"I/O Controller Connected {self.port_name}")

            # Start a thread to read from the serial port
            self.running = True
            self.read_thread = threading.Thread(target=self.read_loop)
            self.read_thread.daemon = True
            self.read_thread.start()

            return True
        except Exception as ex:
            self.write_line(f"Error opening port: {ex}")
            return False

    def close(self):
        """Close the serial connection"""
        self.running = False
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)

        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.write_line(f"I/O Controller Disconnected {self.port_name}")

    def write_out(self, command: OutPorts, state: PortState) -> bool:
        """Send a command to the output port"""
        result = False

        if not self.is_open():
            self.write_line("Cannot send command - port is not open")
            return result

        # Check if trying to use ports > 4 when in FourPorts mode
        if self.io_type == IOType.FourPorts and command.value > OutPorts.Out_4.value:
            self.write_line(f"Cannot use {command} with Four Ports mode")
            return result

        try:
            bytes_to_send = bytearray(
                [0x98, self.port_out[command.value], state.value, 0x99]
            )
            self.write_line(
                f"Sending raw data: {' '.join([f'{b:02X}' for b in bytes_to_send])}"
            )
            self.serial_port.write(bytes_to_send)
            self.serial_port.flush()  # Đảm bảo dữ liệu được gửi đi
            self.write_line(f"I/O Controller Send {command}, State {state}")
            result = True
        except Exception as ex:
            self.write_line(f"Error writing to port: {ex}")

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
                    self.write_line(
                        f"Raw data received: {' '.join([f'{b:02X}' for b in buffer])}"
                    )
                    if len(buffer) >= 3:  # Chỉ xử lý nếu đủ 3 byte
                        self.process_in_data(buffer)

                # Small delay to prevent high CPU usage
                time.sleep(0.1)
            except Exception as ex:
                self.write_line(f"Error reading from port: {ex}")
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
                        self.write_line(debug_str)

                    # Small delay to prevent high CPU usage
                    time.sleep(0.1)
                except Exception as ex:
                    self.write_line(f"Error reading from port: {ex}")
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
            self.write_line(f"Unknown input byte: {temp:02X}")
            return

        # Determine state based on whether value increased or decreased
        state = PortState.On if buffer[1] > self.stored_byte_in else PortState.Off

        # Update stored byte
        self.stored_byte_in = buffer[1]

        self.write_line(f"I/O Controller Received {command}, State {state}")

        # Notify callbacks
        event_args = IODataReceivedEventArgs(command, state)
        for callback in self.data_received_callbacks:
            callback(self, event_args)

    def write_line(self, msg: str):
        """Write log message - overridden in GUI application"""
        print(msg)


class IOControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("I/O Controller Interface")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.io_controller = None
        self.input_indicators = {}
        self.output_buttons = {}

        self.create_gui()

    def create_gui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Connection settings frame
        conn_frame = ttk.LabelFrame(main_frame, text="Kết nối", padding=10)
        conn_frame.pack(fill=tk.X, pady=5)

        # COM port selection
        ttk.Label(conn_frame, text="Cổng COM:").grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.port_var = tk.StringVar(value="COM9")
        ttk.Entry(conn_frame, textvariable=self.port_var, width=10).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.W
        )

        # IO Type selection
        ttk.Label(conn_frame, text="Loại I/O:").grid(
            row=0, column=2, padx=5, pady=5, sticky=tk.W
        )
        self.io_type_var = tk.StringVar(value="EightPorts")
        ttk.Combobox(
            conn_frame,
            textvariable=self.io_type_var,
            values=["FourPorts", "EightPorts"],
            width=10,
            state="readonly",
        ).grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)

        # Connect/Disconnect buttons
        self.connect_btn = ttk.Button(conn_frame, text="Kết nối", command=self.connect)
        self.connect_btn.grid(row=0, column=4, padx=5, pady=5)

        self.disconnect_btn = ttk.Button(
            conn_frame, text="Ngắt kết nối", command=self.disconnect, state=tk.DISABLED
        )
        self.disconnect_btn.grid(row=0, column=5, padx=5, pady=5)

        # Create I/O control frame with two columns
        io_control_frame = ttk.Frame(main_frame)
        io_control_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Inputs frame (left side)
        input_frame = ttk.LabelFrame(io_control_frame, text="Input Ports", padding=10)
        input_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        for i in range(1, 9):
            frame = ttk.Frame(input_frame)
            frame.pack(fill=tk.X, pady=2)

            ttk.Label(frame, text=f"In_{i}:").pack(side=tk.LEFT, padx=5)

            indicator = ttk.Label(
                frame, text="●", foreground="gray", font=("Arial", 16)
            )
            indicator.pack(side=tk.LEFT, padx=5)

            self.input_indicators[i] = indicator

        # Outputs frame (right side)
        output_frame = ttk.LabelFrame(io_control_frame, text="Output Ports", padding=10)
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        for i in range(1, 9):
            frame = ttk.Frame(output_frame)
            frame.pack(fill=tk.X, pady=2)

            ttk.Label(frame, text=f"Out_{i}:").pack(side=tk.LEFT, padx=5)

            btn_on = ttk.Button(
                frame,
                text="ON",
                width=5,
                command=lambda port=i: self.send_output(port, PortState.On),
            )
            btn_on.pack(side=tk.LEFT, padx=5)

            btn_off = ttk.Button(
                frame,
                text="OFF",
                width=5,
                command=lambda port=i: self.send_output(port, PortState.Off),
            )
            btn_off.pack(side=tk.LEFT, padx=5)

            self.output_buttons[i] = (btn_on, btn_off)

            # Disable buttons initially
            btn_on.state(["disabled"])
            btn_off.state(["disabled"])

        # Log frame (bottom)
        log_frame = ttk.LabelFrame(main_frame, text="Nhật ký", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state="disabled")

        # All ports controls
        all_ports_frame = ttk.Frame(main_frame)
        all_ports_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            all_ports_frame,
            text="Bật tất cả",
            command=lambda: self.send_output(0, PortState.On),
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            all_ports_frame,
            text="Tắt tất cả",
            command=lambda: self.send_output(0, PortState.Off),
        ).pack(side=tk.LEFT, padx=5)

        # Status bar
        self.status_var = tk.StringVar(value="Đã sẵn sàng")
        status_bar = ttk.Label(
            main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(fill=tk.X, pady=(5, 0))

    def connect(self):
        port_name = self.port_var.get()
        io_type = (
            IOType.EightPorts
            if self.io_type_var.get() == "EightPorts"
            else IOType.FourPorts
        )

        # Create IO controller
        self.io_controller = IOController(port_name=port_name, io_type=io_type)

        # Override the write_line method
        self.io_controller.write_line = self.write_log

        # Register callback
        self.io_controller.add_data_received_callback(self.on_data_received)

        # Try to open connection
        if self.io_controller.open():
            self.status_var.set(f"Đã kết nối đến {port_name}")
            self.connect_btn.state(["disabled"])
            self.disconnect_btn.state(["!disabled"])

            # Enable output buttons
            max_port = 4 if io_type == IOType.FourPorts else 8
            for i in range(1, 9):
                if i <= max_port:
                    self.output_buttons[i][0].state(["!disabled"])
                    self.output_buttons[i][1].state(["!disabled"])
                else:
                    self.output_buttons[i][0].state(["disabled"])
                    self.output_buttons[i][1].state(["disabled"])
        else:
            self.status_var.set(f"Không thể kết nối đến {port_name}")
            self.io_controller = None

    def disconnect(self):
        if self.io_controller:
            self.io_controller.close()
            self.io_controller = None

            # Update UI
            self.status_var.set("Đã ngắt kết nối")
            self.connect_btn.state(["!disabled"])
            self.disconnect_btn.state(["disabled"])

            # Disable all output buttons
            for i in range(1, 9):
                self.output_buttons[i][0].state(["disabled"])
                self.output_buttons[i][1].state(["disabled"])

            # Reset all input indicators
            for i in range(1, 9):
                self.input_indicators[i].configure(foreground="gray")

    def send_output(self, port_num, state):
        if not self.io_controller or not self.io_controller.is_open():
            self.write_log("Không thể gửi lệnh - chưa kết nối")
            return

        port = OutPorts(port_num)
        self.io_controller.write_out(port, state)

    def on_data_received(self, sender, event_args):
        # Update the input indicator in the UI
        if event_args.command != InPorts.All:
            port_num = event_args.command.value
            color = "green" if event_args.state == PortState.On else "gray"

            # Update in the main thread
            self.root.after(0, lambda: self.update_indicator(port_num, color))

    def update_indicator(self, port_num, color):
        if port_num in self.input_indicators:
            self.input_indicators[port_num].configure(foreground=color)

    def write_log(self, message):
        def _update_log():
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")

        # Schedule the update to run in the main thread
        self.root.after(0, _update_log)

    def on_closing(self):
        if self.io_controller:
            self.io_controller.close()
        self.root.destroy()


# Main entry point
def main():
    root = tk.Tk()
    app = IOControllerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
