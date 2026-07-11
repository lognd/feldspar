//! extern "C" symbol-presence smoke test (WO-07, 02-edge-cases "Library +
//! calibration").
//!
//! Approach (a) from the work order: `dlopen` the just-built
//! `feldspar_library` cdylib via `libloading` and resolve every WO-07
//! `extern "C"` symbol by name/arity. Chosen over the `nm` shell-out
//! fallback (b) because `libloading` is a normal Cargo dev-dependency
//! (no external binary the CI image might be missing) and gives a
//! precise arity check via the `Symbol<unsafe extern "C" fn(...) -> f64>`
//! turbofish, not just a substring match on a symbol table.
//!
//! The cdylib is located relative to the current test binary: integration
//! test binaries live at `target/<profile>/deps/<bin>`, so walking up from
//! `current_exe()` to its `deps`-parent directory lands on `target/<profile>/`,
//! where the cdylib (`libfeldspar_library.so`/`.dylib`/`.dll`) sits alongside
//! it. `cargo test` builds this crate only as an `rlib`, never emitting the
//! cdylib, so the test builds it on demand (`ensure_cdylib_built`) rather than
//! relying on a prior `cargo build` -- keeping an isolated `cargo test` green.

// This integration test must call `dlopen`/`dlsym` (via `libloading`) to
// assert extern "C" symbol presence, which is inherently `unsafe`. The
// workspace denies `unsafe_code` in library/binary code (AD-3's `feldspar-
// library` crate itself has none); this test-only opt-out is scoped to
// this file and does not weaken that guarantee anywhere else.
#![allow(unsafe_code)]

use std::path::{Path, PathBuf};
use std::process::Command;

use libloading::{Library, Symbol};

/// Finds `target/<profile>/` by walking up from the current test
/// binary's path (`target/<profile>/deps/<bin>`).
fn target_profile_dir() -> PathBuf {
    let exe = std::env::current_exe().expect("current_exe should resolve for a running test");
    // exe = .../target/<profile>/deps/extern_c_smoke-<hash>
    let deps_dir = exe.parent().expect("test exe has a parent dir");
    deps_dir
        .parent()
        .expect("deps dir has a parent (the profile dir)")
        .to_path_buf()
}

/// Builds the expected cdylib filename for the current platform.
fn cdylib_name() -> &'static str {
    if cfg!(target_os = "linux") {
        "libfeldspar_library.so"
    } else if cfg!(target_os = "macos") {
        "libfeldspar_library.dylib"
    } else {
        "feldspar_library.dll"
    }
}

/// Ensures the cdylib artifact exists, building it on demand if absent.
///
/// `cargo test` compiles this crate only as an `rlib` for the test harness
/// and never emits the `cdylib` output, so an isolated `cargo test` (as CI
/// runs it) finds no `.so` unless a prior `cargo build` happened to leave a
/// stale one behind. Build it explicitly, honoring the active profile
/// inferred from the running test binary's own `target/<profile>/` location,
/// so the test is hermetic regardless of invocation order.
fn ensure_cdylib_built(profile_dir: &Path) {
    if profile_dir.join(cdylib_name()).exists() {
        return;
    }
    let mut cmd = Command::new(env!("CARGO"));
    cmd.args(["build", "-p", "feldspar-library"]);
    // The dev profile lands in `target/debug`; `--release` in `target/release`.
    if profile_dir.file_name().and_then(|n| n.to_str()) == Some("release") {
        cmd.arg("--release");
    }
    let status = cmd
        .status()
        .expect("failed to spawn `cargo build` to produce the cdylib");
    assert!(
        status.success(),
        "`cargo build -p feldspar-library` failed while producing the cdylib"
    );
}

fn locate_cdylib() -> PathBuf {
    let profile_dir = target_profile_dir();
    ensure_cdylib_built(&profile_dir);
    let candidate = profile_dir.join(cdylib_name());
    assert!(
        candidate.exists(),
        "expected built cdylib at {:?} (searched from profile dir {:?}) \
         even after an on-demand `cargo build`",
        candidate,
        profile_dir
    );
    candidate
}

#[test]
fn wo07_extern_c_symbols_resolve_via_dlopen() {
    let path = locate_cdylib();
    let lib =
        unsafe { Library::new(&path) }.unwrap_or_else(|e| panic!("failed to dlopen {path:?}: {e}"));

    unsafe {
        let f: Symbol<unsafe extern "C" fn(f64, f64) -> f64> = lib
            .get(b"rect_second_moment\0")
            .expect("rect_second_moment symbol should resolve");
        assert!((f(0.04, 0.06) - 0.04 * 0.06_f64.powi(3) / 12.0).abs() < 1e-15);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64, f64) -> f64> = lib
            .get(b"cantilever_tip_deflection\0")
            .expect("cantilever_tip_deflection symbol should resolve");
        let _ = f(1000.0, 1.0, 200e9, 8e-6);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64, f64) -> f64> = lib
            .get(b"cantilever_required_youngs_modulus\0")
            .expect("cantilever_required_youngs_modulus symbol should resolve");
        let _ = f(1000.0, 1.0, 8e-6, 1e-3);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64) -> f64> = lib
            .get(b"lame_hoop_stress_bore\0")
            .expect("lame_hoop_stress_bore symbol should resolve");
        let _ = f(30.0, 1.0, 2.0);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64) -> f64> = lib
            .get(b"lame_radial_stress_bore\0")
            .expect("lame_radial_stress_bore symbol should resolve");
        assert_eq!(f(42.0, 1.0, 2.0), -42.0);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64) -> f64> = lib
            .get(b"von_mises_principal\0")
            .expect("von_mises_principal symbol should resolve");
        assert!((f(100.0, 0.0, 0.0) - 100.0).abs() < 1e-12);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64) -> f64> = lib
            .get(b"bore_von_mises\0")
            .expect("bore_von_mises symbol should resolve");
        let _ = f(30.0, 1.0, 2.0);

        // WO-16 additions (vibration tier formulas).
        let f: Symbol<unsafe extern "C" fn(f64, f64) -> f64> = lib
            .get(b"sdof_first_mode\0")
            .expect("sdof_first_mode symbol should resolve");
        let _ = f(1000.0, 2.0);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64, f64, f64) -> f64> = lib
            .get(b"beam_cantilever_first_mode\0")
            .expect("beam_cantilever_first_mode symbol should resolve");
        let _ = f(200e9, 8e-6, 7850.0, 0.01, 1.0);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64) -> f64> = lib
            .get(b"miles_grms\0")
            .expect("miles_grms symbol should resolve");
        let _ = f(100.0, 10.0, 0.1);
        // WO-17 (elec): same AD-3 link-visibility check for the elec
        // formula home, `crates/feldspar-library/src/elec.rs`.
        let f: Symbol<unsafe extern "C" fn(f64, f64, f64, f64) -> f64> = lib
            .get(b"divider_loaded_vout\0")
            .expect("divider_loaded_vout symbol should resolve");
        assert!((f(10.0, 10e3, 10e3, 100e3) - 4.761904761904762).abs() < 1e-9);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64, f64) -> f64> = lib
            .get(b"rc_step_response\0")
            .expect("rc_step_response symbol should resolve");
        let _ = f(5.0, 1000.0, 1e-6, 1e-3);

        let f: Symbol<unsafe extern "C" fn(f64, f64) -> f64> = lib
            .get(b"rlc_resonant_frequency\0")
            .expect("rlc_resonant_frequency symbol should resolve");
        let _ = f(10e-3, 100e-9);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64) -> f64> = lib
            .get(b"rlc_quality_factor\0")
            .expect("rlc_quality_factor symbol should resolve");
        let _ = f(10.0, 10e-3, 100e-9);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64, f64, f64, f64) -> f64> = lib
            .get(b"bjt_bias_collector_current\0")
            .expect("bjt_bias_collector_current symbol should resolve");
        let _ = f(12.0, 47e3, 10e3, 1e3, 100.0, 0.7);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64) -> f64> = lib
            .get(b"bjt_bias_collector_voltage\0")
            .expect("bjt_bias_collector_voltage symbol should resolve");
        let _ = f(12.0, 1.286e-3, 2.2e3);

        let f: Symbol<unsafe extern "C" fn(f64, f64, f64) -> f64> = lib
            .get(b"nmos_saturation_drain_current\0")
            .expect("nmos_saturation_drain_current symbol should resolve");
        assert!((f(1e-3, 3.0, 1.0) - 2.0e-3).abs() < 1e-12);
    }
}
