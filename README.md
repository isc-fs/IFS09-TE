<img width="470.235" height="179.4" alt="isc-full-primary" src="https://github.com/user-attachments/assets/31365569-11bf-427e-ae3e-8d81ca87d765" />

# IFS09-TE

Hardware design, embedded firmware, and real-time telemetry software for the **Telemetry & Data Acquisition Subsystem** of the **IFS09**, developed for the **ISC Formula Student Racing Team** (Season 2026/2027).

[![Formula Student](https://img.shields.io/badge/Formula%20Student-ISC-yellow.svg)](https://www.comillas.edu/)
[![Season](https://img.shields.io/badge/Season-2026%2F2027-blue.svg)]()
[![Software](https://img.shields.io/badge/GUI-PyQt5%20%7C%20Python%203.11-green.svg)]()
[![Firmware](https://img.shields.io/badge/Firmware-Arduino%20%2F%20STM32-red.svg)]()
[![Hardware](https://img.shields.io/badge/EDA-KiCad%208.x-orange.svg)]()

---

## Subsystem Architecture

```
+-----------------------------------------------------------------------------------------+
|                                     IFS09 RACE CAR                                      |
|  [Sensors & CAN Bus] ---> [ECU / VCU] ---> [Telemetry TX: nRF24L01+ PA+LNA]            |
+---------------------------------------------------+-------------------------------------+
                                                    |
                                             2.4 GHz RF Link
                                        (Trackside Line-of-Sight)
                                                    |
+---------------------------------------------------v-------------------------------------+
|                         IFS09 TELEMETRY RECEIVER (BASE STATION)                         |
|                                                                                         |
|  [External 2.4GHz Antenna] ===> [SMA Jack] ===> [nRF24L01+ PA+LNA Module]               |
|                                                        |                                |
|                                                    SPI Bus                              |
|                                                        v                                |
|                                              [Arduino Nano 3.0]                         |
|                                                 (ATmega328P)                            |
|                                                        |                                |
|                                              USB-C Serial (115200)                      |
|                                                        v                                |
|                                    [Ground Station: isc_realtime_26]                    |
+-----------------------------------------------------------------------------------------+
```

---

## Repository Structure

```
IFS09-TE/
+-- .github/workflows/          # Team automation workflows (issue tracking, roadmap, CI)
+-- isc_realtime_26/            # Real-time telemetry monitoring GUI & data acquisition
¦   +-- ui.py                   # Main PyQt5 dashboard & diagnostics UI
¦   +-- ISC_RTT_serial.py       # Serial communication, framing & packet decoding
¦   +-- ISC_RTT_demo.py         # Offline simulation / bench demo generator
¦   +-- isc_marple.py           # Real-time cloud sync with Marple analytics
¦   +-- ISC_RTT.spec            # PyInstaller distribution build specification
¦   +-- docs / guides           # Guides and Work Orders (Word/PDF)
+-- firmware/                   # Embedded firmware
¦   +-- RTT_nano_26/            # Current Season 09 Telemetry Receiver Arduino firmware
¦   +-- RTT_nano/               # Historical receiver firmware & high-range variants
¦   +-- nrf24/                  # STM32 transmitter firmware for telemetry radio node
+-- hardware/                   # Hardware EDA projects & documentation
¦   +-- IFS09-TeleReceiver/     # KiCad PCB project, schematics, layout, and production files
¦   +-- docs/                   # Block diagrams, pinout diagrams, 3D PCB renders
¦   +-- *.pdf                   # Schematics (v1.0 & v2.0), Design Reports, and Work Orders
+-- ROADMAP.md                  # Telemetry subsystem season roadmap & milestones
+-- README.md                   # This documentation
```

---

## Getting started

1. Create a GitHub account if you don't have one yet.
2. Download and install [GitHub Desktop](https://desktop.github.com/) (beginner) or [Git CLI](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) (advanced).
   - If this is your first time using GitHub Desktop, make sure to read the [User Manual](https://help.github.com/desktop/guides/).
   - If this is your first time using Git, start with a tutorial:
     - [Git Tutorial](https://git-scm.com/docs/gittutorial)
     - [Atlassian Git Tutorial](https://www.atlassian.com/git/tutorials/)
   - Keep a copy of [GitHub's Git Cheat Sheet](https://services.github.com/kit/downloads/github-git-cheat-sheet.pdf) handy as a reference.

3. Clone this repository to your machine:
   - **SSH:** `git@github.com:isc-fs/IFS09-TE.git`
   - **HTTPS:** `https://github.com/isc-fs/IFS09-TE.git`

---

## Running the Real-Time Telemetry Software (`isc_realtime_26`)

### Requirements
- Python 3.11+
- Virtual environment recommended:

```bash
cd isc_realtime_26
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install --upgrade pip
pip install pyinstaller pyqt5 matplotlib numpy pyserial requests openpyxl influxdb-client pandas marpledata
```

### Launching the Dashboard
- **Live vehicle / bench mode:**
  ```bash
  python ui.py
  ```
- **Demo / simulation mode:**
  ```bash
  python ISC_RTT_demo.py
  ```

---

## How we work with this repository

### Main branches

The repository follows standard ISC branching rules:

- **`main`** is the production branch. It contains only validated code, schematics, and firmware ready for track operations. Never work directly on it.
- **`dev`** is the development branch. It is the integration point where everyone's work comes together. Never work directly on it either — all changes arrive through a feature branch.

```
main  ------------------?----------------------?--?  (validated releases only)
                        ?                      ?
dev   ------?---?---?---?---?---?---?---?---?--?--?  (continuous integration)
            ?   ?       ?   ?   ?       ?   ?
          feat/1 fix/1 feat/2 fix/2   feat/3 fix/3
```

### Feature branches

All work — whether a new feature or a bug fix — is done on a **feature branch** created from `dev`. When the work is ready, a Pull Request is opened toward `dev`, reviewed, merged, and the branch is deleted.

There are two branch types, each with its own independent numeric counter:

```
feat/<n>   ?  new functionality  (feat/1, feat/2, feat/3 ...)
fix/<n>    ?  bug fix            (fix/1,  fix/2,  fix/3  ...)
```

The `feat` and `fix` counters are independent: `feat/2` and `fix/2` can exist at the same time with no conflict.

### Tracking branch history

Feature branches are deleted after merging to keep the repository clean. The history of each branch is preserved in **GitHub Issues**.

Every branch has one associated issue. The issue carries a **label** (`feat` or `fix`) and its title includes the branch number, for example: `[feat/3] Add CAN broadcast for mission state`. When the branch is merged and deleted, the issue is closed — becoming a permanent record of all the work done.

---

## Automation

The repository includes GitHub Actions workflows that manage tracking issues automatically. No setup is required — it works for every developer as soon as they create a branch.

- **Automatic issue creation:** When a `feat/*` or `fix/*` branch is pushed, an issue is opened with template sections and assigned labels.
- **Wrong number warning:** Validates that branch numbering increments monotonically.
- **Auto-fill description:** The first commit message automatically populates the issue description.
- **Roadmap synchronization:** Updates subsystem progress in `ROADMAP.md`.

---

## Step-by-step workflow

1. **Create the branch:**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feat/1    # or fix/1
   ```
2. **Push the branch:**
   ```bash
   git push origin feat/1
   ```
   The tracking issue will be opened automatically on GitHub.

3. **Work and commit:**
   ```bash
   git add .
   git commit -m "feat(telemetry): describe your changes clearly"
   git push origin feat/1
   ```

4. **Open a Pull Request:**
   Target `dev`, write `Closes #<issue-number>` in the description, verify no errors, and request subsystem review.

---

*ISC Racing Team — IFS09*
