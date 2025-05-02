# Installation Guide

Follow these steps to set up the Akita Meshtastic IRC Gateway (AMIG) on your system.

## Prerequisites

* **Python:** Version 3.8 or higher is recommended.
* **Pip:** Python's package installer (usually included with Python).
* **Git:** For cloning the repository.
* **(Optional but Recommended)** A Meshtastic device configured and operational.

## Steps

1.  **Clone the Repository:**
    Open your terminal or command prompt and clone the project repository:
    ```bash
    git clone <your-repository-url> # Replace with the actual URL
    cd meshtastic-irc-gateway # Or your chosen directory name
    ```

2.  **Create Virtual Environment (Recommended):**
    Using a virtual environment keeps project dependencies isolated.
    ```bash
    # Create the environment (e.g., named 'venv')
    python -m venv venv

    # Activate the environment
    # On Linux/macOS:
    source venv/bin/activate
    # On Windows (cmd.exe):
    venv\Scripts\activate.bat
    # On Windows (PowerShell):
    .\venv\Scripts\Activate.ps1
    ```
    You should see `(venv)` prepended to your terminal prompt, indicating the virtual environment is active.

3.  **Install Dependencies:**
    Install the required Python packages listed in `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```
    This will install `irc`, `meshtastic`, `pypubsub`, and `requests`.

4.  **Configure the Gateway:**
    * Locate the configuration file: `src/gateway/config.py`.
    * **Edit `config.py`** with your preferred text editor.
    * **Crucially, set up your Meshtastic device connection:**
        * For a **Serial/USB** connection, set `MESH_DEVICE_PORT` to the correct port name (e.g., `MESH_DEVICE_PORT = "/dev/ttyUSB0"` or `MESH_DEVICE_PORT = "COM3"`). Leave `MESH_DEVICE_HOST` as `None`.
        * For a **TCP/IP** connection (device on WiFi), set `MESH_DEVICE_HOST` to the device's IP address (e.g., `MESH_DEVICE_HOST = "192.168.1.100"`). Leave `MESH_DEVICE_PORT` as `None`.
        * *If both are left as `None`, the gateway will use the Mock Interface for testing.*
    * **(Required for WEATHER command)** Set `WEATHER_API_KEY` with your key obtained from [OpenWeatherMap](https://openweathermap.org/appid). You can set it directly or via an environment variable.
    * **(Required for WEATHER command)** Verify or change `WEATHER_LOCATION` to your desired location.
    * Review other settings like `IRC_SERVER_PORT`, `IRC_SERVER_NAME`, `CONTROL_CHANNEL` and adjust if needed.

5.  **Install Documentation Tools (Optional):**
    If you want to build or serve the documentation locally:
    ```bash
    pip install mkdocs mkdocs-material
    ```

## Next Steps

With the gateway installed and configured, proceed to the **[Running the Gateway](running.md)** guide.
