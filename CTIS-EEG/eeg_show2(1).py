import tkinter as tk
from tkinter import messagebox, filedialog
import serial
import threading
import binascii
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import numpy as np
import time


class BluetoothSerialApp:
    def __init__(self, master):
        self.master = master
        self.master.title("EEG Data Acquisition and Visualization")
        self.master.geometry("800x800")

        # 设置数据采集参数
        self.sample_rate = 512  # Hz
        self.display_duration = 40  # 秒
        self.buffer_size = self.sample_rate * self.display_duration

        # 电压转换系数
        self.conversion_factor = 1.8 / (4096 * 2000) * 1000000  # 转换为微伏(µV)

        # 初始化数据缓冲区
        self.raw_data_buffer = bytearray()  # 用于存储未处理的原始数据
        self.eeg_data = deque([0] * self.buffer_size, maxlen=self.buffer_size)
        self.timestamps = deque(np.linspace(-self.display_duration, 0, self.buffer_size),
                                maxlen=self.buffer_size)

        # 原始数据记录相关
        self.raw_data_file = None
        self.is_recording_raw = False
        self.raw_data_filename = ""
        self.raw_packet_count = 0  # 记录数据包数量

        # 创建图形界面
        self.create_widgets()

        # 初始化串口和其它变量
        self.serial_port = None
        self.is_reading = False
        self.download_path = ""
        self.collect_count = 1  # 采集文件计数器
        self.last_update_time = time.time()
        self.update_interval = 0.05  # 图表更新间隔(秒)
        self.start_time = time.time()  # 记录开始时间
        self.data_points_received = 0  # 记录接收到的数据点数量

    def create_widgets(self):
        # 创建主框架
        main_frame = tk.Frame(self.master)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建脑电曲线图
        self.create_eeg_plot(main_frame)

        # 创建控制面板
        control_frame = tk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(10, 5))

        # 串口号输入
        port_frame = tk.Frame(control_frame)
        port_frame.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(port_frame, text="COM Port:").pack(side=tk.LEFT)
        self.port_entry = tk.Entry(port_frame, width=10)
        self.port_entry.insert(0, "COM3")
        self.port_entry.pack(side=tk.LEFT, padx=5)

        # 按钮框架
        button_frame = tk.Frame(control_frame)
        button_frame.pack(side=tk.LEFT)

        self.start_button = tk.Button(button_frame, text="Start", command=self.start_reading, width=8)
        self.start_button.pack(side=tk.LEFT, padx=2)

        self.pause_button = tk.Button(button_frame, text="Pause", command=self.pause_reading, width=8)
        self.pause_button.pack(side=tk.LEFT, padx=2)
        self.pause_button.config(state=tk.DISABLED)

        self.collect_button = tk.Button(button_frame, text="Save Processed", command=self.collect_data, width=12)
        self.collect_button.pack(side=tk.LEFT, padx=2)

        self.raw_collect_button = tk.Button(button_frame, text="Save Raw", command=self.collect_raw_data, width=8)
        self.raw_collect_button.pack(side=tk.LEFT, padx=2)

        self.settings_button = tk.Button(button_frame, text="Settings", command=self.open_settings, width=8)
        self.settings_button.pack(side=tk.LEFT, padx=2)

        self.clear_button = tk.Button(button_frame, text="Clear", command=self.clear_display, width=8)
        self.clear_button.pack(side=tk.LEFT, padx=2)

        # 数据显示区域
        display_frame = tk.Frame(main_frame)
        display_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # 原始数据框
        data_frame = tk.Frame(display_frame)
        data_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(data_frame, text="Raw Data (Voltage Values in µV)", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.data_display = tk.Text(data_frame, height=8, wrap=tk.WORD, font=("Courier", 9),
                                    bg="black", fg="white")
        scrollbar = tk.Scrollbar(data_frame, orient="vertical", command=self.data_display.yview)
        self.data_display.configure(yscrollcommand=scrollbar.set)

        self.data_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(5, 0))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 状态栏
        status_frame = tk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        tk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X)

    def create_eeg_plot(self, parent):
        # 创建脑电曲线图
        plot_frame = tk.Frame(parent)
        plot_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tk.Label(plot_frame, text="Real-time EEG Signal (40 seconds)", font=("Arial", 10, "bold")).pack(anchor=tk.W)

        # 创建Matplotlib图形
        self.fig, self.ax = plt.subplots(figsize=(10, 4))
        self.fig.subplots_adjust(bottom=0.15, left=0.1, right=0.95, top=0.95)

        # 初始化空数据
        self.line, = self.ax.plot([], [], 'b-', linewidth=0.8)

        # 设置图表属性（使用英文标签）
        self.ax.set_xlim(-self.display_duration, 0)
        self.ax.set_ylim(-100, 100)  # 调整Y轴范围以适应转换后的电压值
        self.ax.set_xlabel('Time (seconds)')
        self.ax.set_ylabel('Voltage (µV)')
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.set_title('EEG Signal')

        # 嵌入到Tkinter窗口
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def open_settings(self):
        # 设置窗口
        self.settings_window = tk.Toplevel(self.master)
        self.settings_window.title("Settings")
        self.settings_window.geometry("400x200")
        self.settings_window.transient(self.master)
        self.settings_window.grab_set()

        # 下载路径设置
        path_frame = tk.Frame(self.settings_window)
        path_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Label(path_frame, text="Save Path:").pack(anchor=tk.W)

        path_entry_frame = tk.Frame(path_frame)
        path_entry_frame.pack(fill=tk.X, pady=(5, 0))

        self.download_entry = tk.Entry(path_entry_frame)
        self.download_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if self.download_path:
            self.download_entry.insert(0, self.download_path)

        tk.Button(path_entry_frame, text="Browse", command=self.browse_download_path, width=8).pack(side=tk.RIGHT,
                                                                                                    padx=(5, 0))

        # 按钮框架
        button_frame = tk.Frame(self.settings_window)
        button_frame.pack(side=tk.BOTTOM, pady=10)

        tk.Button(button_frame, text="Save", command=self.save_settings, width=10).pack(side=tk.RIGHT, padx=5)
        tk.Button(button_frame, text="Cancel", command=self.settings_window.destroy, width=10).pack(side=tk.RIGHT)

    def browse_download_path(self):
        path = filedialog.askdirectory()
        if path:
            self.download_entry.delete(0, tk.END)
            self.download_entry.insert(0, path)

    def save_settings(self):
        self.download_path = self.download_entry.get()
        if self.download_path:
            messagebox.showinfo("Settings", "Save path set successfully!")
            self.settings_window.destroy()
        else:
            messagebox.showwarning("Warning", "Please set a valid save path.")

    def start_reading(self):
        # 开始读取数据
        port = self.port_entry.get()
        if not port:
            messagebox.showwarning("Warning", "Please enter COM port!")
            return

        # 检查保存路径
        if not self.download_path:
            messagebox.showwarning("Warning", "Please set save path first in Settings.")
            return

        try:
            self.serial_port = serial.Serial(port, 115200, timeout=0.1)
            self.is_reading = True
            self.start_time = time.time()  # 重置开始时间
            self.data_points_received = 0  # 重置数据点计数
            self.raw_packet_count = 0  # 重置数据包计数器
            self.status_var.set("Reading data...")
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)

            # 清空数据缓冲区
            self.raw_data_buffer = bytearray()

            # 启动数据读取线程
            self.read_thread = threading.Thread(target=self.read_data, daemon=True)
            self.read_thread.start()

            # 启动图表更新
            self.update_plot()

        except Exception as e:
            messagebox.showerror("Error", f"Cannot open serial port: {str(e)}")

    def read_data(self):
        # 实时读取数据
        while self.is_reading and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    self.process_incoming_data(data)
            except Exception as e:
                print(f"Error reading data: {e}")
                break

        self.status_var.set("Data reading stopped")

    def process_incoming_data(self, data):
        # 处理传入的原始数据
        self.raw_data_buffer.extend(data)

        # 处理数据包
        self.process_data_packets()

    def process_data_packets(self):
        # 处理完整的数据包
        i = 0
        packets_processed = 0

        while i < len(self.raw_data_buffer):
            # 检查是否有足够的数据来识别包类型
            if i + 4 <= len(self.raw_data_buffer):
                # 检查是否是小包头 (AA AA 04 80)
                if (self.raw_data_buffer[i] == 0xAA and
                        self.raw_data_buffer[i + 1] == 0xAA and
                        self.raw_data_buffer[i + 2] == 0x04 and
                        self.raw_data_buffer[i + 3] == 0x80):

                    # 小包长度是8字节
                    if i + 8 <= len(self.raw_data_buffer):
                        # 提取整个小包数据
                        small_packet = self.raw_data_buffer[i:i + 8]

                        # 保存原始数据包到缓冲区（如果正在记录）
                        if self.is_recording_raw and self.raw_data_file:
                            self.save_raw_packet(small_packet)

                        # 处理小包数据
                        self.process_small_packet(small_packet)

                        packets_processed += 1
                        i += 8
                    else:
                        # 数据不足，等待更多数据
                        break

                # 检查是否是大包头 (AA AA 20 02)
                elif (self.raw_data_buffer[i] == 0xAA and
                      self.raw_data_buffer[i + 1] == 0xAA and
                      self.raw_data_buffer[i + 2] == 0x20 and
                      self.raw_data_buffer[i + 3] == 0x02):

                    # 大包长度是38字节（根据您提供的示例）
                    if i + 38 <= len(self.raw_data_buffer):
                        # 提取整个大包数据
                        large_packet = self.raw_data_buffer[i:i + 38]

                        # 保存原始数据包到缓冲区（如果正在记录）
                        if self.is_recording_raw and self.raw_data_file:
                            self.save_raw_packet(large_packet)

                        # 大包不用于EEG数据显示，只记录
                        i += 38
                    else:
                        # 数据不足，等待更多数据
                        break
                else:
                    # 不是有效的包头，移动一个字节
                    i += 1
            else:
                # 数据不足以检查包头，等待更多数据
                break

        # 移除已处理的数据
        if i > 0:
            self.raw_data_buffer = self.raw_data_buffer[i:]

        # 更新状态栏
        if packets_processed > 0:
            self.status_var.set(f"Receiving data: {self.data_points_received} points, Packets: {self.raw_packet_count}")

    def process_small_packet(self, packet):
        """处理小包数据"""
        if len(packet) != 8:
            return

        # 提取数据
        num1 = packet[5]
        num2 = packet[6]
        num3 = packet[7]

        # 计算校验和
        checksum = ((0x80 + 0x02 + num1 + num2) ^ 0xFFFFFFFF) & 0xFF

        if checksum == num3:
            # 计算原始数据值
            rawdata = (num1 << 8) | num2
            if rawdata > 32768:
                rawdata -= 65536

            # 应用电压转换公式
            voltage_uV = rawdata * self.conversion_factor

            # 添加到脑电数据队列
            self.eeg_data.append(voltage_uV)
            self.data_points_received += 1

            # 显示处理后的电压值
            if self.data_points_received % 10 == 0:  # 每10个点更新一次显示
                self.data_display.insert(tk.END, f"{voltage_uV:.2f}\n")
                self.data_display.see(tk.END)

    def save_raw_packet(self, packet):
        """将原始数据包保存到文件"""
        if not self.raw_data_file:
            return

        # 将字节转换为十六进制字符串
        hex_str = ' '.join(f'{b:02X}' for b in packet)

        # 写入文件
        self.raw_data_file.write(hex_str + '\n')
        self.raw_data_file.flush()  # 确保数据立即写入文件

        self.raw_packet_count += 1

    def update_plot(self):
        # 更新脑电曲线图
        if self.is_reading:
            current_time = time.time()

            # 控制更新频率
            if current_time - self.last_update_time >= self.update_interval:
                # 计算相对时间
                elapsed_time = current_time - self.start_time

                # 生成时间轴数据
                time_data = np.linspace(-min(elapsed_time, self.display_duration), 0, len(self.eeg_data))

                # 更新曲线
                self.line.set_data(time_data, list(self.eeg_data))

                # 调整X轴范围
                self.ax.set_xlim(-min(elapsed_time, self.display_duration), 0)

                # 自动调整Y轴范围
                if len(self.eeg_data) > 0:
                    y_min = min(self.eeg_data)
                    y_max = max(self.eeg_data)
                    margin = max(10, (y_max - y_min) * 0.1)  # 至少10µV的边距
                    self.ax.set_ylim(y_min - margin, y_max + margin)

                # 重绘图表
                self.canvas.draw()

                self.last_update_time = current_time

            # 继续更新
            self.master.after(10, self.update_plot)

    def pause_reading(self):
        # 暂停读取
        self.is_reading = False
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)

        # 停止原始数据记录
        if self.is_recording_raw and self.raw_data_file:
            self.is_recording_raw = False
            self.raw_data_file.close()
            self.raw_data_file = None
            self.status_var.set(f"Paused. Raw packets saved: {self.raw_packet_count}")

        if self.serial_port:
            self.serial_port.close()

        self.status_var.set("Paused")

    def collect_data(self):
        # 采集处理后的数据到文件
        if not self.download_path:
            messagebox.showwarning("Warning", "Please set save path first.")
            return

        filename = f"{self.download_path}/processed_eeg_data_{time.strftime('%Y%m%d_%H%M%S')}.txt"

        try:
            with open(filename, "w") as f:
                # 写入文件头
                f.write("Processed EEG Data Acquisition\n")
                f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Sample Rate: {self.sample_rate} Hz\n")
                f.write(f"Conversion Factor: {self.conversion_factor}\n")
                f.write("Time(ms),Voltage(uV)\n")

                # 写入时间戳和脑电数据
                for i, value in enumerate(self.eeg_data):
                    # 计算时间戳 (毫秒)
                    timestamp = i * (1000 / self.sample_rate)
                    f.write(f"{timestamp:.2f},{value:.2f}\n")

            messagebox.showinfo("Data Saved", f"Processed data successfully saved to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Error saving file: {str(e)}")

    def collect_raw_data(self):
        # 采集原始数据包到文件
        if not self.download_path:
            messagebox.showwarning("Warning", "Please set save path first.")
            return

        if self.is_recording_raw and self.raw_data_file:
            # 如果正在记录，则停止记录并保存
            self.is_recording_raw = False
            self.raw_data_file.close()
            self.raw_data_file = None
            messagebox.showinfo("Raw Data Saved",
                                f"Raw data collection stopped. Total packets: {self.raw_packet_count}")
        else:
            # 开始记录原始数据
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.raw_data_filename = f"{self.download_path}/raw_eeg_packets_{timestamp}.txt"
            try:
                self.raw_data_file = open(self.raw_data_filename, "w")
                self.is_recording_raw = True
                self.raw_packet_count = 0  # 重置数据包计数器

                # 写入文件头信息
                header = f"Raw EEG Data Packets - Started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                header += f"COM Port: {self.port_entry.get()}, Baud Rate: 115200\n"
                header += "Format: Hex string of each packet (small: 8 bytes, large: 38 bytes)\n"
                header += "=" * 60 + "\n"
                self.raw_data_file.write(header)
                self.raw_data_file.flush()

                messagebox.showinfo("Raw Data Recording",
                                    f"Started recording raw data packets to {self.raw_data_filename}")
                self.status_var.set(f"Recording raw data packets...")

            except Exception as e:
                messagebox.showerror("Error", f"Cannot create raw data file: {str(e)}")

    def clear_display(self):
        # 清空显示
        self.data_display.delete("1.0", tk.END)

        # 重置数据队列
        self.eeg_data = deque([0] * self.buffer_size, maxlen=self.buffer_size)

        # 重置图表
        self.line.set_data([], [])
        self.ax.set_xlim(-self.display_duration, 0)
        self.ax.set_ylim(-100, 100)
        self.canvas.draw()

        # 重置计数器
        self.data_points_received = 0

        self.status_var.set("Display cleared")


if __name__ == "__main__":
    root = tk.Tk()
    app = BluetoothSerialApp(root)
    root.mainloop()