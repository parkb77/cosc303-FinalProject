
The Master Purchase List


Component Category	Item Name / Example Option	Estimated Cost	Hardware Role & Purpose
Motor Control	Dual Motor Driver Board (TB6612FNG)
(e.g., SparkFun, Adafruit, or generic breakout)	$5 – $15	Acts as the electronic muscle. Translates the Raspberry Pi's low-power logic into high-current power to spin the Roomba motors.
Power Management	DC-to-DC Buck Converter (Step-Down Regulator)
(Input: 6V-30V, Output: 5V / 3A to 5A minimum)	$8 – $15	Safely steps down the Roomba's heavy 14.4V battery down to a perfectly regulated 5V to power your Raspberry Pi 4B without causing brownouts.
Wiring & Prototyping	Premium Jumper Wires & Small Breadboard
(Female-to-Female & Male-to-Female assortments)	$10	Crucial for clean routing from the Pi's GPIO pins to the motor driver breakout board.
Electrical Safety	Inline Fuse Holder with 3A or 5A Fuse	$5	Placed between the 14.4V Roomba battery and your electronics to protect your Pi 4B and driver from permanent damage if a short circuit occurs.
Structural / Mounts	M3 Nylon Standoff and Screw Kit	$10	For securely mounting the Raspberry Pi 4B and motor driver to the internal plastic chassis framework of the gutted j8.


📋 Technical Requirements List & Core Motivations

To successfully implement the C++ code for coordinate tracking (x, y), your physical hardware integration and software structure must meet the following baseline conditions:

1. Software Stack Requirements

• Operating System: Ubuntu 22.04 LTS (64-bit) Server or Desktop installed on the Pi 4B's MicroSD card.
	• Motivation: You cannot use standard Raspberry Pi OS. ROS 2 development binaries are officially compiled and optimized strictly for specific Ubuntu Long-Term Support (LTS) environments.
• ROS 2 Distribution: ROS 2 Humble Hawksbill.
	• Motivation: This distribution perfectly pairs with Ubuntu 22.04 and offers the most robust, bug-free C++ client library (rclcpp) ecosystem for custom motor odometry writing.

2. Electronic Integration Requirements

• Shared Ground Architecture: A thick physical wire must jump from a GND pin on the Raspberry Pi directly to the GND pin on the TB6612FNG Motor Driver, which must also tie back to the Negative (-) terminal of the Roomba Battery.
	• Motivation: Without a single, unified reference point for 0 Volts across the whole robot, the digital PWM pulses sent by your C++ code will floating-signal drift, resulting in erratic, stuttering, or entirely non-responsive wheel motors.
• Hardware Interrupt-Capable GPIO Pins: The Roomba wheel encoder pins must be wired into specific GPIO pins on the Pi 4B that can handle high-frequency software interrupts (e.g., GPIO 17, 18, 27, 22).
	• Motivation: The wheel encoders flash digital pulses hundreds of times per second as the robot drives. Standard software scanning loops are too slow and drop ticks. Your C++ code must leverage hardware interrupts to instantly count every single tick to calculate an exact 5-meter travel limit.

3. Power Isolation Requirements

• Independent Electronic Rails: The 14.4V battery power must split into two parallel lanes. One lane routes through the inline fuse directly to the motor driver's VM pin. The second lane goes through the Buck Converter to step down to 5V, which exclusively enters the Pi 4B via its USB-C port or 5V/GND headers.
	• Motivation: Motors are electrically noisy loads. When they instantly shift directions or start moving to complete a vector command, they create massive reverse-voltage spikes. Isolating the Pi behind a dedicated regulator prevents it from instantly resetting or crashing mid-execution.
