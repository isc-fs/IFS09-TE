"""
tests/test_sync.py — Test Suite for Tick-to-Time Multi-Log Synchronization

Covers:
  1. Synthetic tick rollover math (16-bit, 32-bit, multi-wrap).
  2. Cross-correlation offset matching under latency, jitter, and noise.
  3. Vectorized resampling completeness (zero unexpected NaNs, strict shape adherence).
  4. End-to-end MultiLogSynchronizer integration (Session + AMS + IMU).
"""

import numpy as np
import pandas as pd
import pytest

from core.sync import (
    MultiLogSynchronizer,
    cross_correlate_offset,
    resample_signals,
    unwrap_ticks,
)


# ==============================================================================
# 1. TICK ROLLOVER TESTS
# ==============================================================================

def test_unwrap_ticks_no_wrap():
    """Verify strictly monotonic ticks pass through unmodified."""
    raw = np.array([0, 100, 250, 500, 1000], dtype=np.int64)
    unwrapped = unwrap_ticks(raw, bit_width=16)
    np.testing.assert_array_equal(unwrapped, raw)


def test_unwrap_ticks_16bit_single_overflow():
    """Verify single 16-bit overflow (modulus 65536) is correctly resolved."""
    # Counter wraps from 65530 to 5
    raw = np.array([65500, 65520, 65535, 5, 25, 100], dtype=np.int64)
    expected = np.array([65500, 65520, 65535, 65536 + 5, 65536 + 25, 65536 + 100], dtype=np.int64)

    unwrapped = unwrap_ticks(raw, bit_width=16)
    np.testing.assert_array_equal(unwrapped, expected)


def test_unwrap_ticks_16bit_multiple_overflows():
    """Verify multiple consecutive 16-bit rollovers."""
    mod = 65536
    raw = np.array([
        mod - 10,
        mod - 5,
        2,              # Wrap 1
        1000,
        mod - 2,
        15,             # Wrap 2
        mod - 50,
        1,              # Wrap 3
        500
    ], dtype=np.int64)

    unwrapped = unwrap_ticks(raw, bit_width=16)
    diffs = np.diff(unwrapped)
    # Every consecutive step must be strictly positive
    assert np.all(diffs > 0), f"Unwrapped diffs not strictly positive: {diffs}"
    assert unwrapped[-1] > 3 * mod


def test_unwrap_ticks_32bit():
    """Verify 32-bit counter overflow (modulus 4,294,967,296)."""
    mod = 2**32
    raw = np.array([mod - 100, mod - 20, 50, 200], dtype=np.int64)
    expected = np.array([mod - 100, mod - 20, mod + 50, mod + 200], dtype=np.int64)

    unwrapped = unwrap_ticks(raw, bit_width=32)
    np.testing.assert_array_equal(unwrapped, expected)


# ==============================================================================
# 2. CROSS-CORRELATION OFFSET VALIDATION UNDER LATENCY & JITTER
# ==============================================================================

def test_cross_correlate_offset_perfect_alignment():
    """Verify 0.0s offset detected when two signals are identical and in-phase."""
    t = np.linspace(0, 10, 500)
    sig = np.sin(2 * np.pi * 1.5 * t) + 0.5 * np.cos(2 * np.pi * 4.0 * t)

    offset_s, r = cross_correlate_offset(sig, sig, t, t, max_lag_s=5.0)
    assert abs(offset_s) < 0.02, f"Expected ~0s offset, got {offset_s}"
    assert r > 0.95, f"Expected high correlation, got {r}"


def test_cross_correlate_offset_injected_latency_and_noise():
    """
    Inject known time delay (+3.450s) and random Gaussian jitter/noise.
    Verify offset recovery is accurate within ±30ms and correlation is robust.
    """
    np.random.seed(42)
    t_ref = np.linspace(0, 30, 1500)  # 50 Hz, 30 seconds
    # Rich signal with multi-tone sine and step transitions (simulating throttle/current bursts)
    base_sig = np.sin(2 * np.pi * 0.5 * t_ref) + 0.8 * np.sin(2 * np.pi * 2.2 * t_ref)
    base_sig += np.where((t_ref > 5) & (t_ref < 12), 4.0, 0.0)
    base_sig += np.where((t_ref > 18) & (t_ref < 24), -3.0, 0.0)

    true_delay_s = 3.450  # External log started with a delay of 3.450s

    # Generate external log sampled at a different rate (e.g. 73 Hz) with delay and noise
    t_ext = np.linspace(0, 30, 2200)
    ext_sig = np.interp(t_ext - true_delay_s, t_ref, base_sig)
    # Add 10% Gaussian noise
    ext_sig += np.random.normal(0, 0.2, size=len(ext_sig))

    offset_s, r = cross_correlate_offset(base_sig, ext_sig, t_ref, t_ext, max_lag_s=10.0)

    # Note: ext_aligned_time = t_ext + offset_s = t_ref -> offset_s should equal -true_delay_s
    error_ms = abs(offset_s - (-true_delay_s)) * 1000.0
    assert error_ms < 40.0, f"Offset recovery error too high: {error_ms:.2f} ms (expected {-true_delay_s}, got {offset_s})"
    assert r > 0.80, f"Expected strong correlation under noise, got {r}"


# ==============================================================================
# 3. VECTORIZED RESAMPLING COMPLETENESS
# ==============================================================================

def test_resample_signals_completeness():
    """Assert 0 unexpected NaNs, strict shape match, and accurate linear interpolation."""
    s_time = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    s_df = pd.DataFrame({
        'voltage': [300.0, 310.0, 330.0, 320.0, 340.0],
        'temperature': [25.0, 26.0, 28.0, 27.5, 30.0],
        'state_flag': [1, 1, 2, 2, 3],
    })

    t_time = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5])

    res = resample_signals(
        source_df=s_df,
        source_time_s=s_time,
        target_time_s=t_time,
        continuous_cols=['voltage', 'temperature'],
        discrete_cols=['state_flag'],
    )

    # 1. Shape match
    assert len(res) == len(t_time)
    assert set(res.columns) == {'voltage', 'temperature', 'state_flag'}

    # 2. Completeness (zero NaNs)
    assert res.isna().sum().sum() == 0, f"Unexpected NaNs found: {res.isna().sum()}"

    # 3. Interpolation accuracy at midpoint 0.5s: voltage should be 305.0
    assert pytest.approx(res.loc[1, 'voltage'], 0.01) == 305.0
    # Clamped edge at 4.5s: voltage should be clamped to 340.0
    assert pytest.approx(res.loc[9, 'voltage'], 0.01) == 340.0


# ==============================================================================
# 4. END-TO-END MULTI-LOG SYNCHRONIZATION INTEGRATION
# ==============================================================================

def test_multilog_synchronizer_end_to_end(tmp_path):
    """
    Synthesize base telemetry session, external AMS SD-card log, and IMU log.
    Execute MultiLogSynchronizer and verify comprehensive integration.
    """
    n_rows = 300
    t_sec = np.linspace(0, 15, n_rows)

    # 1. Base session
    # Simulated current burst
    current = 20.0 + 80.0 * np.sin(2 * np.pi * 0.2 * t_sec)**2
    # Simulated acceleration
    accel = 0.5 * np.sin(2 * np.pi * 0.3 * t_sec)

    session_df = pd.DataFrame({
        'time_elapsed_s': t_sec,
        'tick_ms': (t_sec * 1000).astype(int),
        'corriente_accu': current,
        'imu_ax_g': accel,
        'inv_rpm': (t_sec * 200).astype(int),
    })

    # 2. External AMS log (with 16-bit tick rollover and +1.5s delay)
    ams_delay = 1.5
    ams_t = np.linspace(0, 15, 250)
    # Ticks with 16-bit wrap simulation: start near 65400
    raw_ams_ticks = (65400 + (ams_t * 1000).astype(int)) % 65536

    ams_current = np.interp(ams_t - ams_delay, t_sec, current * 1000.0)  # in mA

    ams_df = pd.DataFrame({
        'tick_ms': raw_ams_ticks,
        'I_filt_mA': ams_current,
        't0_0': 35.5 + 2.0 * ams_t,
        't0_1': 36.0 + 2.1 * ams_t,
        'v0_0': 3800 + (ams_t * 10).astype(int),
    })

    # 3. External IMU log (with -0.8s offset)
    imu_delay = -0.8
    imu_t = np.linspace(0, 15, 400)
    imu_ax = np.interp(imu_t - imu_delay, t_sec, accel)
    imu_df = pd.DataFrame({
        'time_elapsed_s': imu_t,
        'ax': imu_ax,
        'ay': imu_ax * 0.5,
        'az': np.ones_like(imu_ax) * 9.81,
        'gx': np.zeros_like(imu_ax),
    })

    out_file = tmp_path / "test_session_merged.csv"

    sync_engine = MultiLogSynchronizer(tick_bit_width=16)
    merged_df, summary = sync_engine.synchronize(
        session_input=session_df,
        ams_input=ams_df,
        imu_input=imu_df,
        output_path=out_file,
    )

    # Assert output file created
    assert out_file.exists()

    # Assert row count preserved
    assert len(merged_df) == n_rows

    # Assert new channels integrated
    assert 'ams_t_mod0_cell0' in merged_df.columns
    assert 'ams_t_mod0_cell1' in merged_df.columns
    assert 'ams_v_mod0_cell0' in merged_df.columns
    assert 'imu_ext_ax_g' in merged_df.columns
    assert 'imu_ext_ay_g' in merged_df.columns

    # Assert zero unexpected NaNs
    assert merged_df['ams_t_mod0_cell0'].isna().sum() == 0
    assert merged_df['imu_ext_ax_g'].isna().sum() == 0

    # Verify summary contents
    assert 'AMS' in summary.streams
    assert 'IMU' in summary.streams
    assert summary.streams['AMS'].success is True
    assert summary.streams['IMU'].success is True
    assert summary.total_rows == n_rows
    assert summary.duration_s == pytest.approx(15.0, 0.1)


# ==============================================================================
# 5. REGRESSION & DEMO TESTS
# ==============================================================================

def test_merge_ams_temps_into_session_object_dtype_coercion(tmp_path):
    """
    Verify merge_ams_temps_into_session handles object/string dtype tick_ms columns
    without throwing pandas.errors.MergeError.
    """
    import ISC_RTT_serial as rtt

    session_path = tmp_path / "test_session.csv"
    ams_path = tmp_path / "test_ams.csv"

    # Session CSV with mixed string/object ticks (e.g. empty notes row)
    session_data = {
        'tick_ms': ['100', '200', '300', '', '500'],
        'corriente_accu': [10.5, 20.0, 30.2, '', 50.0],
        'v_cell_min_mV': [3800, 3750, 3700, '', 3600],
    }
    pd.DataFrame(session_data).to_csv(session_path, index=False)

    # AMS CSV with headers and module thermistors
    ams_data = {
        'tick_ms': [100, 200, 300, 500],
        'I_filt_mA': [10500, 20000, 30200, 50000],
        'vmin_mV': [3800, 3750, 3700, 3600],
        't0_0': [25.1, 25.2, 25.3, 25.4],
        't0_1': [26.0, 26.1, 26.2, 26.3],
    }
    pd.DataFrame(ams_data).to_csv(ams_path, index=False)

    success, msg, *rest = rtt.merge_ams_temps_into_session(session_path, ams_path)
    assert success is True
    assert "AMS Temps merged" in msg


def test_demo_generator_log_replay(tmp_path):
    """
    Verify DemoDataGenerator starts, loads candidates, generates snapshots, and stops cleanly.
    """
    import time
    import ISC_RTT_demo

    gen = ISC_RTT_demo.DemoDataGenerator()
    gen.start(use_marple=False, piloto="TestPilot", circuito="TestTrack")
    time.sleep(0.5)
    assert gen.running is True
    assert gen.logger is not None
    gen.stop()
    assert gen.running is False
