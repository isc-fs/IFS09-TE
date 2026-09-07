# WORK ORDER: IFS09 TELEMETRY RECEIVER PCB DESIGN & VALIDATION

**Document ID:** WO-IFS09-TEL-001  
**Project:** Formula Student — IFS09 Telemetry System  
**Subsystem:** Telemetry Base Station Receiver (RX)  
**Author / Team:** Electronics Subsystem / ISC Telemetry Team  
**Date:** August 2026  
**Status:** DRAFT / FOR REVIEW  
**Estimated Length:** ~3 Pages  

---

## 1. Executive Summary & Functional Description

### 1.1 Purpose
The purpose of this Work Order is to define the architectural specifications, hardware design requirements, manufacturing constraints, and validation test procedures for the **IFS09 Telemetry Receiver Board**. This custom PCB functions as the ground-station telemetry receiver responsible for capturing real-time vehicle dynamics, powertrain diagnostics, and battery management data transmitted by the IFS09 race car, and forwarding this telemetry stream to a ground station computer over USB-Serial.

### 1.2 System Overview & Operating Principle
The receiver board interfaces two primary active modules:
1. **Processing & USB Interface Unit (Arduino Nano 3.0 / ATmega328P with USB-C):**
   - Employs an **ATmega328P** 8-bit microcontroller (operating at 16 MHz, 5 V logic).
   - Manages SPI transactions with the wireless transceiver, unpacks telemetry payload frames, checks data integrity, and streams raw telemetry packets to a ground PC over a high-speed UART-to-USB-C bridge (e.g., CH340X or FTDI / CP2102 depending on the Nano variant).
   - Serves as the primary 5 V power distribution node received via the USB-C bus.

2. **Long-Range RF Transceiver (nRF24L01+ PA + LNA Module):**
   - Operates in the 2.4 GHz ISM band using GFSK modulation with integrated **Power Amplifier (PA)** and **Low-Noise Amplifier (LNA)** for enhanced link margin and receiver sensitivity (up to -95 dBm @ 250 kbps).
   - Driven via hardware SPI (`MOSI`, `MISO`, `SCK`) with dedicated GPIOs for Chip Enable (`CE`) and Chip Select Not (`CSN`), with an optional Interrupt Request line (`IRQ`).
   - Requires a clean, decoupled 3.3 V power rail capable of supplying peak burst currents (up to ~115–150 mA) without causing brownout or packet drops.

---

## 2. System Architecture & Block Diagram

*(Diagram reserved for author implementation — Block Diagram / Schematic Overview)*

```
+-----------------------------------------------------------------------------+
|                                                                             |
|                                                                             |
|                                                                             |
|                       [ SYSTEM ARCHITECTURE DIAGRAM ]                       |
|                               (Reserved Area)                               |
|                                                                             |
|                                                                             |
|                                                                             |
+-----------------------------------------------------------------------------+
```

---

## 3. Hardware & Design Requirements

### 3.1 Core Component Requirements
- **MCU Sub-module:** Footprint/header socket to mount a standard **Arduino Nano 3.0** with a native **USB-C connector**.
- **RF Sub-module:** 2×4 pin (2.54 mm pitch) standard header socket for an **nRF24L01+ PA+LNA module**.
- **Antenna Interface:** Chassis-mountable / edge-mount **SMA Female (Jack) connector** (50 $\Omega$ impedance) matched for an external 2.4 GHz omnidirectional whip antenna (RP-SMA or SMA depending on module variation).
- **Power Regulation & Decoupling:**
  - Dedicated on-board low-dropout regulator (LDO, 5V $\rightarrow$ 3.3V, e.g., AMS1117-3.3 or AP2112K) to provide stable 3.3 V to the nRF24L01+ module independently of the Arduino Nano internal 3.3V rail.
  - Bulk decoupling: High-value electrolytic/tantalum capacitor ($10\,\mu\text{F} - 47\,\mu\text{F}$) and low-ESR ceramic capacitor ($100\,\text{nF}$) placed in close proximity across the nRF24L01+ $V_{CC}$ and $GND$ pins.

### 3.2 Signal Interfacing & Pinout
| Signal Name | Arduino Nano Pin | nRF24L01+ Pin | Function / Description |
| :--- | :--- | :--- | :--- |
| **VCC_5V** | 5V / VIN | — | 5V Bus derived from USB-C |
| **VCC_3V3** | 3V3 (or LDO OUT) | VCC (Pin 2) | Clean 3.3V Power Supply |
| **GND** | GND | GND (Pin 1) | Common Ground Plane |
| **CE** | D9 (or D8) | CE (Pin 3) | Chip Enable (RX/TX control) |
| **CSN** | D10 (SS) | CSN (Pin 4) | SPI Chip Select Not |
| **SCK** | D13 | SCK (Pin 5) | SPI Serial Clock |
| **MOSI** | D11 | MOSI (Pin 6) | SPI Master Out Slave In |
| **MISO** | D12 | MISO (Pin 7) | SPI Master In Slave Out |
| **IRQ** | D2 (INT0) | IRQ (Pin 8) | Optional Data Ready Interrupt |

### 3.3 Testability Requirements (Test Points)
Dedicated surface mount / through-hole loop test points (min. 1.0 mm pad diameter, labeled on silkscreen) must be included for:
- `TP_5V`: USB 5.0 V input supply.
- `TP_3V3`: nRF24L01+ 3.3 V regulated supply rail.
- `TP_GND`: Primary circuit ground reference.
- `TP_SCK`, `TP_MOSI`, `TP_MISO`: SPI bus verification.
- `TP_CE`, `TP_CSN`: Control signals.
- `TP_UART_TX`, `TP_UART_RX`: Serial debugging lines.

### 3.4 Mechanical & Enclosure Constraints
- **Mounting Holes:** Four (4) symmetric mounting holes designed for **M3 threaded heat-set inserts or screws** (3.2 mm drill diameter, clearance for M3 bolt head/washer).
- **PCB Dimensions:** Compact rectangular form factor optimized to fit inside a custom **3D-printed enclosure** (PLA/PETG).
- **Connector Access:** Edge clearance provided for:
  1. Direct, unblocked insertion of the USB-C cable into the Arduino Nano.
  2. SMA connector extension protruding through the enclosure wall for external antenna attachment.
  3. Status indicator LEDs visible via enclosure light pipes or top surface.

---

## 4. Verification & Testing Requirements

Each manufactured board unit must undergo the following sequential testing protocol before sign-off and deployment:

```mermaid
flowchart LR
    A[Step 1: Power Rail Verification] --> B[Step 2: SPI & RF Init Test]
    B --> C[Step 3: USB-Serial Stream Test]
    C --> D[Step 4: Vehicle Dynamic Range Test]
```

### 4.1 Test Procedure 1: Power Supply Verification (Passive & Active)
- **Objective:** Ensure no short circuits exist and supply voltages remain within operational tolerances.
- **Tools:** Digital Multimeter (DMM), Bench Power Supply (Current Limited at 500 mA) / USB-C Supply.
- **Acceptance Criteria:**
  - Resistance across `TP_5V` to `TP_GND` and `TP_3V3` to `TP_GND` $> 10\,\text{k}\Omega$ before power-up.
  - $V(TP\_5V) = 5.00\,\text{V} \pm 0.25\,\text{V}$.
  - $V(TP\_3V3) = 3.30\,\text{V} \pm 0.10\,\text{V}$ with peak ripple $< 30\,\text{mV}_{p-p}$ under RF transmission burst.

### 4.2 Test Procedure 2: MCU to Transceiver Interface Test
- **Objective:** Verify SPI bus integrity and successful initialization of the nRF24L01+ register map.
- **Tools:** Logic Analyzer / Oscilloscope, Arduino IDE / PlatformIO Serial Debugger.
- **Acceptance Criteria:**
  - Execution of `radio.begin()` returns `TRUE`.
  - `radio.isChipConnected()` validates presence of nRF24L01+.
  - Clean SPI clock edge on `TP_SCK` without ringing or overshoot $> 0.5\,\text{V}$.

### 4.3 Test Procedure 3: Serial Communication & PuTTY Data Transfer Test
- **Objective:** Confirm reliable, uncorrupted serial telemetry transfer to the base station PC.
- **Tools:** PC running PuTTY / Serial Terminal (configured at 115200 baud, 8-N-1, No Parity).
- **Acceptance Criteria:**
  - Board connects over USB-C and enumerates virtual COM port without driver failure.
  - PuTTY displays continuous formatted telemetry stream (e.g., JSON / CSV frame format) with 0% framing errors or dropped packets over a 10-minute continuous run.

### 4.4 Test Procedure 4: Operational Range & Car Link Test
- **Objective:** Validate RF link budget and packet reception rate (PRR) in track conditions.
- **Tools:** IFS09 telemetry transmitter on the vehicle / test rig, external 2.4 GHz antenna, ground PC.
- **Acceptance Criteria:**
  - Packet Reception Rate (PRR) $\ge 95\%$ at line-of-sight distance $\ge 300\,\text{m}$.
  - Reliable link maintained throughout the entire FSAE/Formula Student autocross/endurance track perimeter under vehicle engine/inverter EMI conditions.

---

## 5. Test Execution Sign-Off Sheet

| Test Item | Verification Method | Target Value / Criteria | Measured Value | Pass / Fail | Inspector | Date |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. 5V Supply Rail** | DMM at `TP_5V` | $4.75\text{V} - 5.25\text{V}$ | | | | |
| **2. 3.3V Supply Rail**| DMM at `TP_3V3` | $3.20\text{V} - 3.40\text{V}$ | | | | |
| **3. SPI Communication**| Register Check via SW | `isChipConnected() == true` | | | | |
| **4. USB-Serial Stream**| PuTTY @ 115200 Baud | Zero frame errors / 10 min | | | | |
| **5. Field Range Test** | Track test with vehicle | PRR $\ge 95\%$ @ 300m | | | | |

---

## 6. Post-Design Requirement: Design Report

Upon completion of the PCB layout, hardware fabrication, and initial bench testing, a comprehensive **Design Report** document must be completed and submitted. 

The Design Report must document:
- Final schematic, PCB layout top/bottom layer routing, and ground plane implementation.
- Bill of Materials (BOM) detailing exact component footprints, part numbers, and tolerances.
- 3D enclosure integration details and connector clearance verification.
- Complete bench and track test results recorded using the Section 5 Sign-Off Sheet, including oscilloscope captures and link budget measurements.
- Design iterations, issues encountered during assembly, and recommendations for future revisions.
