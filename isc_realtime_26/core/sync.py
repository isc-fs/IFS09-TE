"""
core/sync.py — Tick-to-Time Multi-Log Synchronization Engine for ISCmetrics

Provides:
  • Vectorized tick rollover unwrapping for hardware counters (16-bit, 32-bit).
  • High-performance FFT cross-correlation offset matching with parabolic sub-sample refinement.
  • Vectorized resampling of asynchronous telemetry streams onto a master monotonic time grid.
  • MultiLogSynchronizer high-level orchestrator for base telemetry, IMU, and AMS logs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import scipy.signal

logger = logging.getLogger("ISC_SYNC")


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class SyncStreamResult:
    """Summary of synchronization results for an individual auxiliary stream."""
    stream_name: str
    success: bool
    offset_ms: float = 0.0
    correlation_score: float = 0.0
    total_records: int = 0
    matched_records: int = 0
    time_span_s: float = 0.0
    message: str = ""


@dataclass
class SyncSummary:
    """Overall summary of a multi-log synchronization operation."""
    session_file: str
    output_file: str
    total_rows: int
    duration_s: float
    streams: Dict[str, SyncStreamResult] = field(default_factory=dict)
    added_columns: List[str] = field(default_factory=list)

    @property
    def all_successful(self) -> bool:
        return all(s.success for s in self.streams.values()) if self.streams else False


# ==============================================================================
# 1. TICK ROLLOVER RESOLUTION
# ==============================================================================

def unwrap_ticks(
    raw_ticks: Union[np.ndarray, pd.Series, List[int]],
    bit_width: int = 32,
    tick_rate_hz: float = 1000.0,
) -> np.ndarray:
    """
    Unwrap monotonic counter ticks that wrap at 2^bit_width.

    Parameters:
      raw_ticks: 1D array of non-negative integer ticks.
      bit_width: Counter resolution (typically 16 for 16-bit timers or 32 for STM32 SysTick).
      tick_rate_hz: Tick frequency (default 1000.0 Hz = 1 tick per ms).

    Returns:
      1D np.ndarray (int64) with continuous monotonic ticks across all rollover events.
    """
    ticks = np.asarray(raw_ticks, dtype=np.int64)
    if len(ticks) <= 1:
        return ticks.copy()

    modulus = int(1 << bit_width) if bit_width < 64 else 0
    if modulus <= 0:
        return ticks.copy()

    # Forward modular deltas: (ticks[i] - ticks[i-1]) % modulus
    # For any forward-running hardware counter, delta is strictly in [0, modulus).
    deltas = (ticks[1:] - ticks[:-1]) % modulus

    unwrapped = np.empty_like(ticks, dtype=np.int64)
    unwrapped[0] = ticks[0]
    unwrapped[1:] = ticks[0] + np.cumsum(deltas)

    return unwrapped



# ==============================================================================
# 2. CROSS-CORRELATION OFFSET MATCHING
# ==============================================================================

def cross_correlate_offset(
    ref_signal: np.ndarray,
    ext_signal: np.ndarray,
    ref_time_s: np.ndarray,
    ext_time_s: np.ndarray,
    max_lag_s: float = 60.0,
    dt_interim_s: float = 0.02,
) -> Tuple[float, float]:
    """
    Compute optimal time offset between two asynchronous signals using FFT cross-correlation.

    Returns:
      (optimal_offset_s, correlation_coefficient)
      where ext_aligned_time = ext_time_s + optimal_offset_s
    """
    ref_sig = np.asarray(ref_signal, dtype=np.float64)
    ext_sig = np.asarray(ext_signal, dtype=np.float64)
    ref_t = np.asarray(ref_time_s, dtype=np.float64)
    ext_t = np.asarray(ext_time_s, dtype=np.float64)

    # Sanity checks
    if len(ref_sig) < 5 or len(ext_sig) < 5:
        return 0.0, 0.0

    # Relative time offsets from start of each stream
    t_ref_rel = ref_t - ref_t[0]
    t_ext_rel = ext_t - ext_t[0]

    max_dur = max(t_ref_rel[-1], t_ext_rel[-1])
    if max_dur <= 0:
        return 0.0, 0.0

    # Common interim regular grid for cross-correlation
    grid = np.arange(0.0, max_dur, dt_interim_s)
    if len(grid) < 10:
        return 0.0, 0.0

    # Vectorized interpolation onto interim grid
    s_ref_interp = np.interp(grid, t_ref_rel, ref_sig, left=ref_sig[0], right=ref_sig[-1])
    s_ext_interp = np.interp(grid, t_ext_rel, ext_sig, left=ext_sig[0], right=ext_sig[-1])

    # Remove DC and standardize
    s_ref_std = np.std(s_ref_interp)
    s_ext_std = np.std(s_ext_interp)

    if s_ref_std < 1e-6 or s_ext_std < 1e-6:
        # One or both signals is flat/constant: correlation cannot identify peak
        return 0.0, 0.0

    s1 = (s_ref_interp - np.mean(s_ref_interp)) / s_ref_std
    s2 = (s_ext_interp - np.mean(s_ext_interp)) / s_ext_std

    # FFT cross-correlation
    corr = scipy.signal.correlate(s1, s2, mode="full", method="fft")
    lags = scipy.signal.correlation_lags(len(s1), len(s2), mode="full") * dt_interim_s

    # Restrict search within [-max_lag_s, max_lag_s]
    valid_mask = np.abs(lags) <= max_lag_s
    if not np.any(valid_mask):
        return 0.0, 0.0

    corr_window = corr[valid_mask]
    lags_window = lags[valid_mask]

    peak_idx = int(np.argmax(corr_window))
    raw_best_lag = lags_window[peak_idx]
    peak_val = corr_window[peak_idx]

    # Normalized cross-correlation score r in [-1, 1]
    norm_factor = np.sqrt(np.sum(s1**2) * np.sum(s2**2))
    r_score = float(peak_val / (norm_factor + 1e-9)) if norm_factor > 0 else 0.0

    # Sub-sample parabolic interpolation around peak
    if 0 < peak_idx < len(corr_window) - 1:
        y0 = corr_window[peak_idx - 1]
        y1 = corr_window[peak_idx]
        y2 = corr_window[peak_idx + 1]
        denom = 2.0 * (2.0 * y1 - y0 - y2)
        if abs(denom) > 1e-9:
            delta = (y2 - y0) / denom
            if abs(delta) < 1.0:
                raw_best_lag += delta * dt_interim_s

    # Absolute offset between ext and ref:
    # t_ref_rel = t_ext_rel + raw_best_lag
    # (ref_t - ref_t[0]) = (ext_t - ext_t[0]) + raw_best_lag
    # ext_t_aligned = ext_t + optimal_offset = ref_t
    optimal_offset_s = (ref_t[0] - ext_t[0]) + raw_best_lag

    return float(optimal_offset_s), float(np.clip(r_score, -1.0, 1.0))


# ==============================================================================
# 3. VECTORIZED RESAMPLING & ALIGNMENT
# ==============================================================================

def resample_signals(
    source_df: pd.DataFrame,
    source_time_s: np.ndarray,
    target_time_s: np.ndarray,
    continuous_cols: Optional[List[str]] = None,
    discrete_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Vectorized resampling of continuous and discrete columns onto target_time_s.
    Zero Python row-iteration loops.
    """
    resampled_data: Dict[str, np.ndarray] = {}

    s_t = np.asarray(source_time_s, dtype=np.float64)
    t_t = np.asarray(target_time_s, dtype=np.float64)

    if len(s_t) == 0:
        empty_cols = (continuous_cols or []) + (discrete_cols or [])
        return pd.DataFrame(index=range(len(t_t)), columns=empty_cols)

    # Sort source strictly monotonic
    if np.any(np.diff(s_t) <= 0):
        sort_idx = np.argsort(s_t)
        s_t = s_t[sort_idx]
        source_df = source_df.iloc[sort_idx]

    # Continuous columns -> 1D linear interpolation with boundary clamp
    if continuous_cols:
        for col in continuous_cols:
            if col in source_df.columns:
                vals = pd.to_numeric(source_df[col], errors='coerce').to_numpy(dtype=np.float64)
                # Fill NaNs in source signal with forward/backward fill before interp
                if np.isnan(vals).any():
                    vals = pd.Series(vals).ffill().bfill().to_numpy()
                resampled_data[col] = np.interp(t_t, s_t, vals, left=vals[0], right=vals[-1])

    # Discrete / categorical columns -> nearest-neighbour / step-function merge_asof
    if discrete_cols:
        disc_existing = [c for c in discrete_cols if c in source_df.columns]
        if disc_existing:
            s_df = pd.DataFrame({'_st': s_t})
            for col in disc_existing:
                s_df[col] = source_df[col].values
            t_df = pd.DataFrame({'_tt': t_t})
            merged_disc = pd.merge_asof(
                t_df,
                s_df,
                left_on='_tt',
                right_on='_st',
                direction='nearest',
            )
            for col in disc_existing:
                # Forward/backward fill edge boundaries to prevent NaNs
                resampled_data[col] = merged_disc[col].ffill().bfill().to_numpy()

    return pd.DataFrame(resampled_data)


# ==============================================================================
# 4. MULTI-LOG SYNCHRONIZER ORCHESTRATOR
# ==============================================================================

class MultiLogSynchronizer:
    """
    High-level orchestrator that merges base telemetry, IMU logs, and AMS logs.
    """

    def __init__(self, tick_bit_width: int = 32, interim_dt_s: float = 0.02):
        self.tick_bit_width = tick_bit_width
        self.interim_dt_s = interim_dt_s

    def synchronize(
        self,
        session_input: Union[str, Path, pd.DataFrame],
        imu_input: Optional[Union[str, Path, pd.DataFrame]] = None,
        ams_input: Optional[Union[str, Path, pd.DataFrame]] = None,
        output_path: Optional[Union[str, Path]] = None,
        gps_input: Optional[Union[str, Path, pd.DataFrame]] = None,
        utc_offset_hours: float = 2.0,
    ) -> Tuple[pd.DataFrame, SyncSummary]:
        """
        Execute multi-log synchronization and return (merged_df, summary).
        """
        # 1. Load base session
        if isinstance(session_input, pd.DataFrame):
            session_df = session_input.copy()
            sess_name = "in_memory_session.csv"
        else:
            session_path = Path(session_input)
            session_df = pd.read_csv(session_path)
            sess_name = session_path.name

        out_name = str(output_path) if output_path else f"{Path(sess_name).stem}_merged.csv"
        added_cols: List[str] = []
        stream_results: Dict[str, SyncStreamResult] = {}

        # Determine reference time grid
        # Preference: elapsed seconds, else relative from tick_ms, else row index / 10 Hz
        if 'time_elapsed_s' in session_df.columns:
            ref_time_s = pd.to_numeric(session_df['time_elapsed_s'], errors='coerce').to_numpy(dtype=np.float64)
        elif 'tick_ms' in session_df.columns:
            raw_ticks = pd.to_numeric(session_df['tick_ms'], errors='coerce').to_numpy(dtype=np.int64)
            unwrapped_ticks = unwrap_ticks(raw_ticks, bit_width=self.tick_bit_width)
            ref_time_s = (unwrapped_ticks - unwrapped_ticks[0]) / 1000.0
        elif 'time' in session_df.columns:
            dts = pd.to_datetime(session_df['time'], errors='coerce')
            ref_time_s = (dts - dts.iloc[0]).dt.total_seconds().to_numpy(dtype=np.float64)
        else:
            ref_time_s = np.arange(len(session_df), dtype=np.float64) * 0.1

        merged_df = session_df.copy()

        # ── 2. SYNCHRONIZE AMS LOG ────────────────────────────────────────────
        if ams_input is not None:
            ams_res, ams_merged_cols = self._sync_ams(merged_df, ams_input, ref_time_s)
            stream_results['AMS'] = ams_res
            added_cols.extend(ams_merged_cols)

        # ── 3. SYNCHRONIZE IMU LOG ────────────────────────────────────────────
        if imu_input is not None:
            imu_res, imu_merged_cols = self._sync_imu(merged_df, imu_input, ref_time_s)
            stream_results['IMU'] = imu_res
            added_cols.extend(imu_merged_cols)

        # ── 4. SYNCHRONIZE GPS LOG (OPTIONAL NMEA / CSV) ──────────────────────
        if gps_input is not None:
            gps_res, gps_merged_cols = self._sync_gps(merged_df, gps_input, utc_offset_hours)
            stream_results['GPS'] = gps_res
            added_cols.extend(gps_merged_cols)

        # ── 5. PERSIST OUTPUT ─────────────────────────────────────────────────
        if output_path is not None:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            merged_df.to_csv(out_p, index=False)

        total_rows = len(merged_df)
        duration_s = float(ref_time_s[-1] - ref_time_s[0]) if len(ref_time_s) > 1 else 0.0

        summary = SyncSummary(
            session_file=sess_name,
            output_file=out_name,
            total_rows=total_rows,
            duration_s=duration_s,
            streams=stream_results,
            added_columns=added_cols,
        )

        return merged_df, summary

    # ── AMS Synchronizer Implementation ───────────────────────────────────────
    def _sync_ams(
        self,
        target_df: pd.DataFrame,
        ams_input: Union[str, Path, pd.DataFrame],
        ref_time_s: np.ndarray,
    ) -> Tuple[SyncStreamResult, List[str]]:
        try:
            if isinstance(ams_input, pd.DataFrame):
                ams_df = ams_input.copy()
            else:
                ams_df = pd.read_csv(Path(ams_input))

            if len(ams_df) == 0:
                return SyncStreamResult("AMS", False, message="AMS log is empty."), []

            # Unwrap ticks
            if 'tick_ms' in ams_df.columns:
                ams_ticks = unwrap_ticks(ams_df['tick_ms'].values, bit_width=self.tick_bit_width)
                ams_time_s = (ams_ticks - ams_ticks[0]) / 1000.0
            elif 'time_elapsed_s' in ams_df.columns:
                ams_time_s = pd.to_numeric(ams_df['time_elapsed_s'], errors='coerce').to_numpy(dtype=np.float64)
            else:
                ams_time_s = np.arange(len(ams_df), dtype=np.float64) * 0.1

            # Select alignment signal
            offset_s = 0.0
            corr_score = 1.0

            ref_sig = None
            ext_sig = None

            # Current match
            if 'corriente_accu' in target_df.columns and 'I_filt_mA' in ams_df.columns:
                ref_sig = target_df['corriente_accu'].to_numpy(dtype=np.float64) * 1000.0
                ext_sig = ams_df['I_filt_mA'].to_numpy(dtype=np.float64)
            elif 'corriente_accu' in target_df.columns and 'current_mA' in ams_df.columns:
                ref_sig = target_df['corriente_accu'].to_numpy(dtype=np.float64) * 1000.0
                ext_sig = ams_df['current_mA'].to_numpy(dtype=np.float64)
            # Voltage match
            elif 'v_cell_min_mV' in target_df.columns and 'vmin_mV' in ams_df.columns:
                ref_sig = target_df['v_cell_min_mV'].to_numpy(dtype=np.float64)
                ext_sig = ams_df['vmin_mV'].to_numpy(dtype=np.float64)

            if ref_sig is not None and ext_sig is not None:
                offset_s, corr_score = cross_correlate_offset(
                    ref_sig, ext_sig, ref_time_s, ams_time_s, max_lag_s=120.0, dt_interim_s=self.interim_dt_s
                )

            aligned_ams_time = ams_time_s + offset_s

            # Identify columns to resample
            # Temperature mapping: t{m}_{c} -> ams_t_mod{m}_cell{c}
            # Voltage mapping: v{m}_{c} -> ams_v_mod{m}_cell{c}
            col_rename = {}
            for col in ams_df.columns:
                if col.startswith('t') and '_' in col and col[1:].replace('_', '').isdigit():
                    m, c = col[1:].split('_', 1)
                    col_rename[col] = f"ams_t_mod{m}_cell{c}"
                elif col.startswith('v') and '_' in col and col[1:].replace('_', '').isdigit():
                    m, c = col[1:].split('_', 1)
                    col_rename[col] = f"ams_v_mod{m}_cell{c}"

            resample_cols = list(col_rename.keys())
            if not resample_cols:
                # Keep numeric columns not already in target
                resample_cols = [c for c in ams_df.select_dtypes(include=[np.number]).columns
                                 if c not in ('tick_ms', 'time_elapsed_s', 'time')]

            resampled = resample_signals(
                ams_df,
                aligned_ams_time,
                ref_time_s,
                continuous_cols=resample_cols,
            )

            # Rename mapped columns
            resampled.rename(columns=col_rename, inplace=True)

            # Insert into target_df
            for col in resampled.columns:
                target_df[col] = resampled[col].values

            result = SyncStreamResult(
                stream_name="AMS",
                success=True,
                offset_ms=round(offset_s * 1000.0, 2),
                correlation_score=round(corr_score, 4),
                total_records=len(ams_df),
                matched_records=len(target_df),
                time_span_s=round(float(ams_time_s[-1] - ams_time_s[0]), 2),
                message=f"AMS merged {len(resampled.columns)} channels (offset={offset_s*1000.0:.1f}ms, r={corr_score:.3f})",
            )
            return result, list(resampled.columns)

        except Exception as e:
            logger.exception("AMS sync failure")
            return SyncStreamResult("AMS", False, message=f"Error: {e}"), []

    # ── IMU Synchronizer Implementation ───────────────────────────────────────
    def _sync_imu(
        self,
        target_df: pd.DataFrame,
        imu_input: Union[str, Path, pd.DataFrame],
        ref_time_s: np.ndarray,
    ) -> Tuple[SyncStreamResult, List[str]]:
        try:
            if isinstance(imu_input, pd.DataFrame):
                imu_df = imu_input.copy()
            else:
                imu_df = pd.read_csv(Path(imu_input))

            if len(imu_df) == 0:
                return SyncStreamResult("IMU", False, message="IMU log is empty."), []

            # Unwrap ticks
            if 'tick_ms' in imu_df.columns:
                imu_ticks = unwrap_ticks(imu_df['tick_ms'].values, bit_width=self.tick_bit_width)
                imu_time_s = (imu_ticks - imu_ticks[0]) / 1000.0
            elif 'time_elapsed_s' in imu_df.columns:
                imu_time_s = pd.to_numeric(imu_df['time_elapsed_s'], errors='coerce').to_numpy(dtype=np.float64)
            else:
                imu_time_s = np.arange(len(imu_df), dtype=np.float64) * 0.01  # default 100 Hz

            offset_s = 0.0
            corr_score = 1.0

            # Match on longitudinal acceleration ax or lateral ay
            if 'imu_ax_g' in target_df.columns and 'ax' in imu_df.columns:
                ref_sig = target_df['imu_ax_g'].to_numpy(dtype=np.float64)
                ext_sig = imu_df['ax'].to_numpy(dtype=np.float64)
                offset_s, corr_score = cross_correlate_offset(
                    ref_sig, ext_sig, ref_time_s, imu_time_s, max_lag_s=60.0, dt_interim_s=self.interim_dt_s
                )
            elif 'imu_ay_g' in target_df.columns and 'ay' in imu_df.columns:
                ref_sig = target_df['imu_ay_g'].to_numpy(dtype=np.float64)
                ext_sig = imu_df['ay'].to_numpy(dtype=np.float64)
                offset_s, corr_score = cross_correlate_offset(
                    ref_sig, ext_sig, ref_time_s, imu_time_s, max_lag_s=60.0, dt_interim_s=self.interim_dt_s
                )

            aligned_imu_time = imu_time_s + offset_s

            # Canonical IMU channels
            imu_cols_map = {
                'ax': 'imu_ext_ax_g',
                'ay': 'imu_ext_ay_g',
                'az': 'imu_ext_az_g',
                'gx': 'imu_ext_gx_dps',
                'gy': 'imu_ext_gy_dps',
                'gz': 'imu_ext_gz_dps',
                'roll': 'imu_ext_roll_deg',
                'pitch': 'imu_ext_pitch_deg',
                'yaw': 'imu_ext_yaw_deg',
            }
            existing_imu_cols = [c for c in imu_cols_map if c in imu_df.columns]
            if not existing_imu_cols:
                existing_imu_cols = [c for c in imu_df.select_dtypes(include=[np.number]).columns
                                     if c not in ('tick_ms', 'time_elapsed_s', 'time')]

            resampled = resample_signals(
                imu_df,
                aligned_imu_time,
                ref_time_s,
                continuous_cols=existing_imu_cols,
            )
            resampled.rename(columns=imu_cols_map, inplace=True)

            for col in resampled.columns:
                target_df[col] = resampled[col].values

            result = SyncStreamResult(
                stream_name="IMU",
                success=True,
                offset_ms=round(offset_s * 1000.0, 2),
                correlation_score=round(corr_score, 4),
                total_records=len(imu_df),
                matched_records=len(target_df),
                time_span_s=round(float(imu_time_s[-1] - imu_time_s[0]), 2),
                message=f"IMU merged {len(resampled.columns)} channels (offset={offset_s*1000.0:.1f}ms, r={corr_score:.3f})",
            )
            return result, list(resampled.columns)

        except Exception as e:
            logger.exception("IMU sync failure")
            return SyncStreamResult("IMU", False, message=f"Error: {e}"), []

    # ── GPS Synchronizer Implementation ───────────────────────────────────────
    def _sync_gps(
        self,
        target_df: pd.DataFrame,
        gps_input: Union[str, Path, pd.DataFrame],
        utc_offset_hours: float,
    ) -> Tuple[SyncStreamResult, List[str]]:
        try:
            from datetime import timedelta
            if isinstance(gps_input, pd.DataFrame):
                gps_df = gps_input.copy()
            else:
                p = Path(gps_input)
                # Check if it's raw NMEA or CSV
                if p.suffix.lower() in ('.nmea', '.log', '.txt'):
                    from ISC_RTT_serial import parse_nmea_log
                    gps_df = parse_nmea_log(p)
                else:
                    gps_df = pd.read_csv(p)

            if len(gps_df) == 0:
                return SyncStreamResult("GPS", False, message="GPS log is empty."), []

            if 'datetime_utc' in gps_df.columns and 'time' in target_df.columns:
                offset = timedelta(hours=utc_offset_hours)
                gps_df['_dt'] = pd.to_datetime(gps_df['datetime_utc'], errors='coerce') + offset
                target_df['_dt'] = pd.to_datetime(target_df['time'], errors='coerce')

                gps_cols = [c for c in ['gps_lat_deg', 'gps_lon_deg', 'gps_speed_kmh', 'gps_course_deg', 'gps_sats', 'gps_fix']
                            if c in gps_df.columns]

                merged = pd.merge_asof(
                    target_df.sort_values('_dt'),
                    gps_df[['_dt'] + gps_cols].sort_values('_dt'),
                    on='_dt',
                    direction='nearest',
                    tolerance=pd.Timedelta(seconds=5),
                )
                target_df.drop(columns=['_dt'], inplace=True, errors='ignore')
                merged.drop(columns=['_dt'], inplace=True, errors='ignore')

                for c in gps_cols:
                    target_df[c] = merged[c].values

                result = SyncStreamResult(
                    stream_name="GPS",
                    success=True,
                    offset_ms=0.0,
                    correlation_score=1.0,
                    total_records=len(gps_df),
                    matched_records=len(target_df),
                    time_span_s=0.0,
                    message=f"GPS merged ({len(gps_cols)} cols, UTC+{utc_offset_hours}h)",
                )
                return result, gps_cols

            return SyncStreamResult("GPS", False, message="Missing timestamp columns for GPS merge"), []
        except Exception as e:
            logger.exception("GPS sync failure")
            return SyncStreamResult("GPS", False, message=f"Error: {e}"), []
