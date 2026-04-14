# Sensor Service

A modular Python-based service for managing, processing, and streaming
sensor data.

## Features

-   Sensor management layer (`manager.py`)
-   Modular sensor drivers (`sensors/`)
-   WebSocket server (`ws/`)
-   Static UI files (`static/`)
-   Configurable system (`config/`)
-   Entry point (`run.py`)

## Project Structure

    sensor/
    ├── run.py
    ├── __init__.py
    ├── config/
    │   ├── __init__.py
    │   └── manager.py
    ├── sensors/
    │   ├── __init__.py
    │   └── ...
    ├── ws/
    │   ├── __init__.py
    │   └── ...
    └── static/

## Installation

    pip install -r requirements.txt

## Run

    python run.py
