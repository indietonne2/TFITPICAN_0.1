#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: setup.py
# Pathname: /path/to/tfitpican/
# Description: Setup script for TFITPICAN dashboard that handles dependencies
#              and configuration for both Mac and Raspberry Pi platforms
# -----------------------------------------------------------------------------

import os
import sys
import platform
import subprocess
import argparse
import json
import shutil
from pathlib import Path

# Define application metadata
APP_NAME = "TFITPICAN"
APP_VERSION = "0.1.0"
DESCRIPTION = "CAN Bus monitoring and visualization dashboard"
AUTHOR = "Thomas Fischer"
LICENSE = "MIT"

# Detect platform
def detect_platform():
    """Detect the current platform"""
    system = platform.system()
    
    if system == "Darwin":
        return "mac"
    elif system == "Linux":
        # Check if we're on a Raspberry Pi
        try:
            with open('/sys/firmware/devicetree/base/model', 'r') as m:
                if 'raspberry pi' in m.read().lower():
                    return "raspberry_pi"
        except:
            pass
        return "linux"
    elif system == "Windows":
        return "windows"
    else:
        return "unknown"

# Requirements for different platforms
REQUIREMENTS = {
    "common": [
        "python-can>=4.0.0",
        "cantools>=36.0.0",
        "PyQt5>=5.15.0",
        "pyqtgraph>=0.12.0",
        "requests>=2.25.0",
        "numpy>=1.20.0",
        "pyyaml>=6.0",
        "influxdb>=5.3.0",
    ],
    "mac": [
        # Mac-specific requirements
    ],
    "raspberry_pi": [
        "RPi.GPIO>=0.7.0",
        "gpiozero>=1.6.2",
    ],
    "linux": [
        # Linux-specific requirements
    ],
    "windows": [
        # Windows-specific requirements
    ]
}

# External services
SERVICES = {
    "influxdb": {
        "description": "Time series database for storing CAN data",
        "required": True,
    },
    "grafana": {
        "description": "Visualization platform for CAN data",
        "required": True,
    },
    "can_utils": {
        "description": "Linux utilities for CAN bus interaction",
        "required": False,
    }
}

# Directory structure
DIR_STRUCTURE = [
    "assets",
    "config",
    "dbc",
    "docs",
    "logs",
    "plugins",
    "scripts",
    "src",
    "src/gui",
    "src/can",
    "src/core",
    "src/db",
    "src/plugins",
    "src/tests",
]

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION} - {DESCRIPTION}")
    parser.add_argument("--install", action="store_true", help="Install requirements")
    parser.add_argument("--init", action="store_true", help="Initialize project directory structure")
    parser.add_argument("--services", action="store_true", help="Install and configure required services")
    parser.add_argument("--can-setup", action="store_true", help="Configure CAN interfaces")
    parser.add_argument("--all", action="store_true", help="Perform all setup steps")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} v{APP_VERSION}")
    
    return parser.parse_args()

def create_directory_structure():
    """Create the project directory structure"""
    print("Creating directory structure...")
    
    for directory in DIR_STRUCTURE:
        os.makedirs(directory, exist_ok=True)
        print(f"  Created: {directory}")
    
    # Create initial config files
    create_default_config()
    
    print("Directory structure created successfully.")

def create_default_config():
    """Create default configuration files"""
    config_dir = "config"
    
    # Main config
    config = {
        "app": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "author": AUTHOR,
            "license": LICENSE
        },
        "can": {
            "interface": "socketcan" if detect_platform() in ["raspberry_pi", "linux"] else "pcan",
            "channel": "can0" if detect_platform() in ["raspberry_pi", "linux"] else "PCAN_USBBUS1",
            "bitrate": 500000,
            "enable_auto_restart": True
        },
        "database": {
            "type": "sqlite",
            "path": "db/tfitpican.db",
            "backup_enabled": True,
            "backup_interval_hours": 24
        },
        "influxdb": {
            "enabled": True,
            "host": "localhost",
            "port": 8086,
            "database": "canbus_data",
            "username": "",
            "password": "",
            "retention_policy": "2w"
        },
        "grafana": {
            "url": "http://localhost:3000",
            "dashboard_uid": "canbus-dashboard"
        },
        "ui": {
            "fullscreen": False,
            "theme": "dark",
            "refresh_rate_ms": 500,
            "show_raw_data": True
        },
        "bluetooth": {
            "enabled": True,
            "device_name": APP_NAME,
            "pin": "1234"
        },
        "logging": {
            "level": "INFO",
            "file_enabled": True,
            "log_dir": "logs",
            "max_size_mb": 10,
            "backup_count": 5
        }
    }
    
    with open(os.path.join(config_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    
    print("  Created: config/config.json")
    
    # Create empty placeholder files
    placeholders = [
        ("dbc/vehicle.dbc", "# DBC file for vehicle CAN messages\n"),
        ("assets/car_diagram.svg", "<!-- SVG car diagram -->\n"),
        ("README.md", f"# {APP_NAME} v{APP_VERSION}\n\n{DESCRIPTION}\n\nAuthor: {AUTHOR}\nLicense: {LICENSE}\n"),
    ]
    
    for path, content in placeholders:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        print(f"  Created: {path}")

def install_requirements():
    """Install required Python packages"""
    platform_type = detect_platform()
    print(f"Installing requirements for platform: {platform_type}")
    
    # Combine common and platform-specific requirements
    requirements = REQUIREMENTS["common"].copy()
    if platform_type in REQUIREMENTS:
        requirements.extend(REQUIREMENTS[platform_type])
    
    # Install with pip
    for req in requirements:
        print(f"Installing {req}...")
        subprocess.run([sys.executable, "-m", "pip", "install", req])
    
    print("Requirements installed successfully.")

def setup_services():
    """Set up required services based on platform"""
    platform_type = detect_platform()
    print(f"Setting up services for platform: {platform_type}")
    
    # Instructions for each platform
    if platform_type == "raspberry_pi" or platform_type == "linux":
        print("\nSetting up InfluxDB and Grafana on Linux/Raspberry Pi:")
        print("1. Install InfluxDB:")
        print("   sudo apt update")
        print("   sudo apt install influxdb")
        print("   sudo systemctl enable influxdb")
        print("   sudo systemctl start influxdb")
        print("\n2. Install Grafana:")
        print("   sudo apt install -y apt-transport-https software-properties-common")
        print("   wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -")
        print("   echo \"deb https://packages.grafana.com/oss/deb stable main\" | sudo tee -a /etc/apt/sources.list.d/grafana.list")
        print("   sudo apt update")
        print("   sudo apt install grafana")
        print("   sudo systemctl enable grafana-server")
        print("   sudo systemctl start grafana-server")
        
    elif platform_type == "mac":
        print("\nSetting up InfluxDB and Grafana on Mac:")
        print("1. Install Homebrew if not already installed:")
        print("   /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        print("\n2. Install InfluxDB:")
        print("   brew install influxdb")
        print("   brew services start influxdb")
        print("\n3. Install Grafana:")
        print("   brew install grafana")
        print("   brew services start grafana")
        
    elif platform_type == "windows":
        print("\nSetting up InfluxDB and Grafana on Windows:")
        print("1. Download and install InfluxDB from:")
        print("   https://portal.influxdata.com/downloads/")
        print("\n2. Download and install Grafana from:")
        print("   https://grafana.com/grafana/download")
    
    print("\nAfter installation, access Grafana at http://localhost:3000 (default credentials: admin/admin)")
    print("Create an InfluxDB datasource in Grafana pointing to http://localhost:8086 and database 'canbus_data'")

def setup_can_interfaces():
    """Set up CAN interfaces based on platform"""
    platform_type = detect_platform()
    print(f"Setting up CAN interfaces for platform: {platform_type}")
    
    if platform_type == "raspberry_pi" or platform_type == "linux":
        print("\nSetting up CAN interfaces on Linux/Raspberry Pi:")
        print("1. Install required packages:")
        print("   sudo apt update")
        print("   sudo apt install can-utils")
        
        print("\n2. For MCP2515-based CAN HAT/Shield, add to /boot/config.txt:")
        print("   dtparam=spi=on")
        print("   dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25")
        
        print("\n3. Configure CAN interface:")
        print("   sudo ip link set can0 up type can bitrate 500000")
        print("   sudo ip link set can0 txqueuelen 1000")
        
        print("\n4. To automatically start CAN at boot, add to /etc/network/interfaces:")
        print("   auto can0")
        print("   iface can0 inet manual")
        print("     pre-up /sbin/ip link set $IFACE type can bitrate 500000")
        print("     up /sbin/ifconfig $IFACE up")
        print("     down /sbin/ifconfig $IFACE down")
        
    elif platform_type == "mac":
        print("\nSetting up CAN interfaces on Mac:")
        print("Mac OS requires external USB-CAN adapters with appropriate drivers.")
        print("1. For PCAN-USB devices:")
        print("   Download drivers from: https://www.peak-system.com/fileadmin/media/mac/")
        print("\n2. For other adapters (CANable, etc.), follow manufacturer instructions.")
        print("\n3. After installing drivers, verify the interface with:")
        print("   python -m can.interfaces.[interface_name].detection")
        
    elif platform_type == "windows":
        print("\nSetting up CAN interfaces on Windows:")
        print("1. For PCAN-USB devices:")
        print("   Download drivers from: https://www.peak-system.com/Downloads.76.0.html")
        print("\n2. For other adapters (Kvaser, etc.), follow manufacturer instructions.")
        print("\n3. After installing drivers, verify the interface with:")
        print("   python -m can.interfaces.[interface_name].detection")
    
    print("\nTest CAN interface with python-can:")
    print("  import can")
    print("  bus = can.interface.Bus(channel='can0', interface='socketcan')")  # Linux example
    print("  msg = can.Message(arbitration_id=0x123, data=[0x01, 0x02, 0x03])")
    print("  bus.send(msg)")

def main():
    """Main entry point"""
    args = parse_args()
    
    print(f"\n{APP_NAME} v{APP_VERSION} - {DESCRIPTION}")
    print(f"Author: {AUTHOR}")
    print(f"License: {LICENSE}")
    print(f"Platform: {detect_platform()}")
    print("-" * 80)
    
    if args.all or args.init:
        create_directory_structure()
    
    if args.all or args.install:
        install_requirements()
    
    if args.all or args.services:
        setup_services()
    
    if args.all or args.can_setup:
        setup_can_interfaces()
    
    if not any([args.all, args.init, args.install, args.services, args.can_setup]):
        print("No action specified. Use --help to see available options.")
    
    print("\nSetup complete!")

if __name__ == "__main__":
    main()
