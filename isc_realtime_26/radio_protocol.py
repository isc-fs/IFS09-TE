"""
radio_protocol -- IFS-09 v4 compact snapshot decoder (pure Python, no GUI/serial deps).

Mirror of ``Core/Src/app/radio_snapshot.cpp`` in IFS09-CE-ECU. One continuous
120-byte snapshot, sent as 5 x 24-byte slices of 32-byte nRF24 payloads:

    [0..3]   tick_ms u32
    [4..5]   flags u16 (see FLAG_* below)
    [6] ctrl_state  [7] ams_fsm_state  [8] inv_state  [9] inv_error  [10] torque_pct
    [11..16] apps1 / apps2 / brake  u16 x3
    [17..18] v_cell_min_mV u16
    [19..35] vmin[5], vmax[5]: 13-bit LSB-first bit-packed (mV)
    [36..39] current_accu_dA i16, current_dcdc_dA i16
    [40]     tmax_dcdc i8      [41..45] tmax_module[5] i8
    [46..47] inv_dc_bus_V u16
    [48..51] inv temps raw u8 (motor1, motor2, pwrstg, board; degC = raw - 50)
    [52..54] inv_rpm i24
    [55..56] inv_pwrstg_bits u16  [57] inv_emctrl_bits u8
    [58..61] torque_est_nm i16, torque_max_feas i16
    [62..63] inv_ac_power i16 (x4 W)
    [64..76] GPS lat i32, lon i32 (deg*1e7), speed u16 (x100), course u16 (x100), sats u8
    [77..92] DTI left, [93..108] DTI right (16 B each)
    [109..113] LWS angle i16 (x10 deg), speed i16 (x10 deg/s), status u8
    [114..119] IMU yaw_rate i16 (x1000 rad/s), a_lat i16 (x100 m/s2), a_long i16 (x100 m/s2)

This module is the single source of truth on the ground-station side and is
imported both by ``ISC_RTT_serial`` (live) and by the firmware round-trip test.
"""
from __future__ import annotations

import math
import struct
from typing import Dict

# ── Wire constants ───────────────────────────────────────────────────────────
MAGIC              = 0xEC
VERSION_SNAPSHOT   = 0x04
KIND_SNAPSHOT      = 0x06
FRAG_SNAPSHOT      = 5
HDR_SIZE           = 8
DATA_SIZE          = 24
PAYLOAD_LEN        = 32
SNAPSHOT_SIZE      = 120

# flags word bit positions
FLAG_START_BUTTON    = 1 << 0
FLAG_T11_8_9         = 1 << 1
FLAG_OK_PRECHARGE    = 1 << 2
FLAG_VCONFIG_ACTIVE  = 1 << 3
FLAG_GPS_FIX         = 1 << 4
FLAG_DTI_L_VALID     = 1 << 5
FLAG_DTI_L_DRIVE_EN  = 1 << 6
FLAG_DTI_L_ERPM_OK   = 1 << 7
FLAG_DTI_R_VALID     = 1 << 8
FLAG_DTI_R_DRIVE_EN  = 1 << 9
FLAG_DTI_R_ERPM_OK   = 1 << 10
FLAG_LWS_VALID       = 1 << 11
FLAG_IMU_VALID       = 1 << 12

# ── IFS-09 drivetrain constants (mirror Core/Src/app/differential_config.c) ──
MOTOR_POLE_PAIRS = 4
GEAR_RATIO       = 12.48
WHEEL_RADIUS_M   = 0.204
G0               = 9.80665

# Legacy EMC inverter eRPM -> speed (kept for the single-inverter bench setup)
_LEGACY_SPEED_K = (11.0 / 32.0) * (2.0 * math.pi / 60.0) * 0.2032 * 3.6


def _u16(d: bytes, o: int) -> int: return struct.unpack_from('<H', d, o)[0]
def _i16(d: bytes, o: int) -> int: return struct.unpack_from('<h', d, o)[0]
def _i32(d: bytes, o: int) -> int: return struct.unpack_from('<i', d, o)[0]
def _u32(d: bytes, o: int) -> int: return struct.unpack_from('<I', d, o)[0]
def _i8(d: bytes, o: int) -> int:  return struct.unpack_from('<b', d, o)[0]


def _i24(d: bytes, o: int) -> int:
    v = d[o] | (d[o + 1] << 8) | (d[o + 2] << 16)
    return v - 0x1000000 if v & 0x800000 else v


def erpm_to_wheel_kmh(erpm: float) -> float:
    """DTI electrical RPM -> wheel linear speed in km/h (signed)."""
    mech_rpm = erpm / MOTOR_POLE_PAIRS
    wheel_rads = (mech_rpm * 2.0 * math.pi / 60.0) / GEAR_RATIO
    return wheel_rads * WHEEL_RADIUS_M * 3.6


def _decode_dti(d: bytes, o: int, prefix: str, valid: bool, drive_en: bool, erpm_ok: bool) -> Dict[str, float]:
    erpm = _i24(d, o)
    mech = erpm / MOTOR_POLE_PAIRS
    return {
        f'{prefix}_erpm':         erpm,
        f'{prefix}_mech_rpm':     round(mech, 1),
        f'{prefix}_wheel_kmh':    round(erpm_to_wheel_kmh(erpm), 2),
        f'{prefix}_duty_pct':     _i16(d, o + 3) / 10.0,
        f'{prefix}_vin_V':        _u16(d, o + 5) / 10.0,
        f'{prefix}_ac_A':         _i16(d, o + 7) / 10.0,
        f'{prefix}_dc_A':         _i16(d, o + 9) / 10.0,
        f'{prefix}_ctrl_temp_C':  _i16(d, o + 11) / 10.0,
        f'{prefix}_motor_temp_C': _i16(d, o + 13) / 10.0,
        f'{prefix}_fault':        d[o + 15],
        f'{prefix}_valid':        int(valid),
        f'{prefix}_drive_en':     int(drive_en),
        f'{prefix}_erpm_valid':   int(erpm_ok),
    }


def decode_snapshot(data: bytes, seq: int = 0) -> dict:
    """Decode a reassembled 120-byte v4 snapshot. Returns {} if too short."""
    if len(data) < SNAPSHOT_SIZE:
        return {}

    flags = _u16(data, 4)
    f = lambda bit: bool(flags & bit)

    # 10 x 13-bit module cell voltages, LSB-first bit stream starting at byte 19.
    stream = int.from_bytes(data[19:36], 'little')
    cells = [(stream >> (13 * i)) & 0x1FFF for i in range(10)]

    gps_has_fix = f(FLAG_GPS_FIX)
    lat_raw, lon_raw = _i32(data, 64), _i32(data, 68)
    spd_raw, crs_raw = _u16(data, 72), _u16(data, 74)

    snap = {
        'tick_ms':            _u32(data, 0),
        'seq':                seq,
        'flags':              flags,
        'start_button':       int(f(FLAG_START_BUTTON)),
        't11_8_9':            int(f(FLAG_T11_8_9)),
        'ok_precharge':       int(f(FLAG_OK_PRECHARGE)),
        'inv_vconfig_active': int(f(FLAG_VCONFIG_ACTIVE)),
        'last_vconfig_tick':  int(f(FLAG_VCONFIG_ACTIVE)),
        'ev_2_3':             0,   # deleted in FS-Rules 2024; kept for CSV/UI compatibility
        'state':              data[6],
        'ctrl_state':         data[6],
        'ams_fsm_state':      data[7],
        'inv_state':          data[8],
        'inv_error':          data[9],
        'dem_code':           data[9],
        'torque_pct':         data[10],
        'apps1_raw':          _u16(data, 11),
        'apps2_raw':          _u16(data, 13),
        'brake_raw':          _u16(data, 15),
        'v_cell_min_mV':      _u16(data, 17),
        'soc':                0,   # no on-car estimator; the GUI derives SoC from voltage
        'vmin_modulo':        cells[0:5],
        'vmax_modulo':        cells[5:10],
        'corriente_accu':     _i16(data, 36) / 10.0,
        'corriente_dcdc':     -_i16(data, 38) / 10.0,
        'temp_dcdc':          _i8(data, 40),
        'temp_max_modulo':    [_i8(data, 41 + i) for i in range(5)],
        'inv_dc_bus_V':       _u16(data, 46),
        # DBC EMC_TX_STATE_5 (0x464): degC = raw - 50. raw 255 -> 205 = sensor N/C.
        'inv_temp_motor1':    data[48] - 50,
        'inv_temp_motor2':    data[49] - 50,
        'inv_temp_pwrstg':    data[50] - 50,
        'inv_temp_board':     data[51] - 50,
        'inv_rpm':            _i24(data, 52),
        'inv_pwrstg_bits':    _u16(data, 55),
        'inv_emctrl_bits':    data[57],
        'emctrl_foc_bitstate': data[57],
        'inv_torque_est_nm':  _i16(data, 58),
        'inv_torque_max_feas': _i16(data, 60),
        'inv_ac_power_W':     _i16(data, 62) * 4,
        # GPS (gate lat/lon/speed on gps_has_fix; the ECU keeps the last valid values)
        'gps_lat_deg':        round(lat_raw / 1e7, 7),
        'gps_lon_deg':        round(lon_raw / 1e7, 7),
        'gps_speed_kmh':      round(spd_raw / 100.0, 2),
        'gps_course_deg':     round(crs_raw / 100.0, 2),
        'gps_sats':           data[76],
        'gps_has_fix':        int(gps_has_fix),
        'gps_lat_deg1e7':     lat_raw,
        'gps_lon_deg1e7':     lon_raw,
        'gps_speed_kmh_x100': spd_raw,
        'gps_course_deg_x100': crs_raw,
    }

    # ── IFS-09 DTI inverters ─────────────────────────────────────────────────
    snap.update(_decode_dti(data, 77, 'dti_l', f(FLAG_DTI_L_VALID), f(FLAG_DTI_L_DRIVE_EN), f(FLAG_DTI_L_ERPM_OK)))
    snap.update(_decode_dti(data, 93, 'dti_r', f(FLAG_DTI_R_VALID), f(FLAG_DTI_R_DRIVE_EN), f(FLAG_DTI_R_ERPM_OK)))

    # ── Bosch LWS ────────────────────────────────────────────────────────────
    snap['lws_angle_deg'] = _i16(data, 109) / 10.0
    snap['lws_speed_dps'] = _i16(data, 111) / 10.0
    snap['lws_status']    = data[113]
    snap['lws_valid']     = int(f(FLAG_LWS_VALID))

    # ── Xsens IMU ────────────────────────────────────────────────────────────
    yaw = _i16(data, 114) / 1000.0
    ay  = _i16(data, 116) / 100.0
    ax  = _i16(data, 118) / 100.0
    snap['imu_yaw_rate_rads'] = yaw
    snap['imu_ay_mps2']       = ay
    snap['imu_ax_mps2']       = ax
    snap['imu_valid']         = int(f(FLAG_IMU_VALID))
    # Keys the legacy Dynamics tab / CSV already consume
    snap['imu_ax_g']   = round(ax / G0, 3)
    snap['imu_ay_g']   = round(ay / G0, 3)
    snap['imu_gz_dps'] = round(math.degrees(yaw), 2)

    # ── Derived drivetrain values ────────────────────────────────────────────
    l_ok = snap['dti_l_valid'] and snap['dti_l_erpm_valid']
    r_ok = snap['dti_r_valid'] and snap['dti_r_erpm_valid']
    speeds = []
    if l_ok: speeds.append(abs(snap['dti_l_wheel_kmh']))
    if r_ok: speeds.append(abs(snap['dti_r_wheel_kmh']))
    if speeds:
        vehicle_kmh = sum(speeds) / len(speeds)
    else:  # fall back to the legacy single-inverter eRPM
        vehicle_kmh = (abs(snap['inv_rpm']) / 10.0) * _LEGACY_SPEED_K
    snap['vehicle_speed_kmh'] = round(vehicle_kmh, 1)
    snap['inv_speed_actual']  = snap['vehicle_speed_kmh']
    snap['dti_speed_delta_kmh'] = round(snap['dti_l_wheel_kmh'] - snap['dti_r_wheel_kmh'], 2) if (l_ok and r_ok) else 0.0
    snap['dti_dc_total_A']    = round(snap['dti_l_dc_A'] + snap['dti_r_dc_A'], 1)
    snap['dti_ac_total_A']    = round(snap['dti_l_ac_A'] + snap['dti_r_ac_A'], 1)
    snap['inv_current_actual'] = snap['dti_dc_total_A']
    return snap
