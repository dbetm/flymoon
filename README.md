# Flymoon

A web app to run locally on a LAN network that checks for possible transits over the Moon or the Sun (up to 15 minutes ahead).

Get flight data from an existing API.

You need to set coordinates for an area to check flights as a bounding box, input your position, choose a target (Moon or Sun), and then the app will compute future flight positions and check intersections with the target, which is called a transit.

![](data/assets/flymoon2.png)


The results show the difference in alt-azimuthal coordinates. Typically, you can expect a likely transit when there's no change in elevation and the difference in altitude (alt diff) and azimuth (az diff) is less than a few grades for both. In such cases, the row of results will be highlighted. Yellow 🟡: Low possibility; Orange 🟠: Medium possibility; Green 🟢: High possibility.


--------


## Setup

**Pre-requisites**

- Python +3.9
- Download or clone this project from GitHub (if you download a zip file, please extract it first, please).

**Linux distros and MacOS**

1) Run setup, this will create a virtual environment and install required python libraries.

```shell
make setup
```

2) Activate virtual env.

```shell
source .venv/bin/activate
```

**Windows**

1) Open the CMD and move to the project path
2) Run this command to create the `.env` file:
```shell
copy .env.mock .env 
```
3) Create a virtual environment:
```shell
python -m venv .venv 
```
4) Activate the virtual environment:
```shell
.venv\Scripts\activate
```
5) Install all the required python dependencies:
```shell
pip install -r requirements.txt
```

**Configuration**

Open the `.env` file. You may need to display the hidden files.

In Windows, if you don't have a text editor to open the `.env` file, you can download and install [Notepad++](https://notepad-plus-plus.org/downloads/)

1) Set `AEROAPI_API_KEY`. Sign up on [FlightAware AeroAPI](https://www.flightaware.com/commercial/aeroapi/) and use the [Personal free tier](https://www.flightaware.com/aeroapi/signup/personal) to generate an API KEY.

2) Set the area of flights to check. I strong suggest to cover a 15 min area. This must be a bounding box, using latitudes and longitudes. Set `LAT_LOWER_LEFT`, `LONG_LOWER_LEFT`, `LAT_UPPER_RIGHT`, and `LONG_UPPER_RIGHT` appropriately.

3) Set your observer position. Set `OBSERVER_LATITUDE`, `OBSERVER_LONGITUDE`, and `OBSERVER_ELEVATION` (in meters). This is where you'll be observing from.

4) (Optional) Set `AUTO_REFRESH_INTERVAL_MINUTES` to configure the default auto-refresh polling interval. Default is 6 minutes, which keeps within FlightAware's free tier rate limits (~10 queries/minute, 500/month). Recommended range: 5-10 minutes for continuous monitoring.

5) (Optional) When using the auto mode If you want to receive notifications in your smartphone, you can get an API KEY from [Pushbucket platform](https://www.pushbullet.com/) and then set `PUSH_BULLET_API_KEY`. To get it, create an account, install the app in your phone and go to *Settings* > *Create Access Token*.


![](data/assets/bounding-box-example.png)


--------


## Usage


**Activate venv**

```shell
source .venv/bin/activate
```

For Windows you can use:
```shell
.venv\Scripts\activate
```

Launch the web server from a terminal.

```shell
python3 app.py
```

Windows:
```shell
python app.py
```

The IP address in LAN network will be displayed, use it to access from any device inside the same network.

Example: `http://192.168.3.199:8000`

**Input your position (coordinates)**

I suggest using [MAPS.ie](https://www.maps.ie/coordinates.html#google_vignette) or [Google Maps](https://maps.google.com/). The values will be saved in local storage, so you won't need to type them again next time if you're in the same location.


**Compute possible transits**

Click on Go! button to display results. Each row will include differences in alt-azimuthal coordinates only if it’s a possible transit. If the difference is enough small, the row will be highlighted in yellow, orange or green color (less probable to more probable).

**Compute possible transits every X minutes**

Click on Auto button, which will require a time in minutes, then the web app will check for transits every X minutes, it there's at leat one possible transit then a sound alert will be played along the sending of a push notification if it was configured (only medium to high probable flighs are notified).

**Change target**

Tap into the target icon and it'll toggle between Sun, Moon, and Auto mode (🌙☀️). Auto mode tracks both targets simultaneously and only shows flights that could transit whichever target is currently above the horizon.

**Map visualization**

Click the 🗺️ button to see an interactive map showing:
- 📍 Your observer position
- Draggable bounding box (drag corners to resize)
- Azimuth arrows: orange for ☀️ sun, blue for 🌙 moon (click for altitude/azimuth)
- Aircraft as ✈️ emoji (rotated to heading) or colored ◆ diamonds for predicted transits
- Transit probability: green = high, orange = medium, yellow = low

**Interactive features:**
- Click an aircraft on the map to flash and scroll to its table row
- Click a table row to flash and pan to the aircraft on the map

**Weather filtering**

If you configure an OpenWeatherMap API key, the app will check cloud cover and skip checking for transits when conditions are poor. Set `OPENWEATHER_API_KEY` in your `.env` file and adjust `CLOUD_COVER_THRESHOLD` (default 30%).


--------


## Background Monitors

For continuous monitoring without keeping a browser open, use the standalone monitors:

**macOS Menu Bar App**
```shell
python3 menubar_monitor.py
```
Shows a moon/sun icon in your menu bar. Click to see status, start/stop monitoring, and view logs.

**Windows System Tray App**
```shell
python windows_monitor.py
```
Shows an icon in your system tray with similar functionality.

**Command Line Monitor**
```shell
python3 monitor.py --latitude 33.0 --longitude -117.3 --elevation 0 --target auto --interval 15
```
Runs in terminal, sends macOS notifications when transits are detected.

All monitors support auto mode (moon+sun), weather filtering, and log transits to CSV files in `data/possible-transits/`.


--------


## Limitations

1) Computing the moment when there is a minimum difference between a plane and the target in alt-azimuthal coordinates is a numerical approach. Perhaps there could be an analytical way to optimize it.

2) The app assumes that airplanes maintain a constant speed and direction. However, changes to these factors within the 15-minute observation window can alter the ETA and potentially disrupt the predicted transit.


--------


## Contribute

This web app is still under active testing. If you want to fix something, improve it, or make a suggestion, feel free to open a Pull Request or an issue.


**Share your epic picture!**

I'd love to watch some transit picture taken with the help of this tool. So, post it on this [issue](https://github.com/dbetm/flymoon/issues/21).

Pro-tip: You can use the Fightradar24 app to complement this web app.